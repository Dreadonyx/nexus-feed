import feedparser
import httpx
from datetime import datetime
from rich.console import Console

console = Console()

HEADERS = {"User-Agent": "nexus-feed/1.0 (github.com/Dreadonyx/nexus-feed)"}
TIMEOUT = httpx.Timeout(10.0)


class Fetcher:
    def __init__(self, config: dict):
        self.config = config
        self.sources_cfg = config.get("sources", {})

    def fetch_all(self) -> list:
        articles = []
        seen_titles = set()

        with httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
            # RSS feeds
            for feed in self.sources_cfg.get("rss", []):
                try:
                    fetched = self._fetch_rss(client, feed["url"], feed["name"])
                    articles.extend(fetched)
                    console.print(f"  [dim]RSS {feed['name']}: {len(fetched)} articles[/dim]")
                except Exception as e:
                    console.print(f"  [yellow]RSS {feed['name']}: {e}[/yellow]")

            # Hacker News
            hn_cfg = self.sources_cfg.get("hackernews", {})
            if hn_cfg.get("enabled", False):
                try:
                    hn = self._fetch_hackernews(client, hn_cfg.get("count", 15), hn_cfg.get("min_points", 50))
                    articles.extend(hn)
                    console.print(f"  [dim]Hacker News: {len(hn)} articles[/dim]")
                except Exception as e:
                    console.print(f"  [yellow]HackerNews: {e}[/yellow]")

            # Reddit
            reddit_cfg = self.sources_cfg.get("reddit", {})
            if reddit_cfg.get("enabled", False):
                for sub in reddit_cfg.get("subreddits", []):
                    try:
                        r = self._fetch_reddit(client, sub, reddit_cfg.get("count", 8))
                        articles.extend(r)
                        console.print(f"  [dim]Reddit r/{sub}: {len(r)} articles[/dim]")
                    except Exception as e:
                        console.print(f"  [yellow]Reddit r/{sub}: {e}[/yellow]")

            # GitHub Trending
            gh_cfg = self.sources_cfg.get("github_trending", {})
            if gh_cfg.get("enabled", False):
                try:
                    gh = self._fetch_github_trending(client)
                    articles.extend(gh)
                    console.print(f"  [dim]GitHub Trending: {len(gh)} articles[/dim]")
                except Exception as e:
                    console.print(f"  [yellow]GitHub Trending: {e}[/yellow]")

        # Dedup by title
        unique = []
        for a in articles:
            key = a["title"].lower().strip()[:60]
            if key and key not in seen_titles:
                seen_titles.add(key)
                unique.append(a)

        return unique

    def _fetch_rss(self, client: httpx.Client, url: str, source_name: str) -> list:
        resp = client.get(url)
        feed = feedparser.parse(resp.text)
        articles = []
        for entry in feed.entries[:12]:
            content = ""
            if hasattr(entry, "summary"):
                content = entry.summary
            elif hasattr(entry, "description"):
                content = entry.description

            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6]).isoformat()
                except Exception:
                    pass

            articles.append({
                "url": entry.get("link", ""),
                "title": self._decode_html(entry.get("title", "")).strip(),
                "source": source_name,
                "content": self._strip_html(content)[:800],
                "published_at": published,
            })
        return [a for a in articles if a["title"] and a["url"]]

    def _fetch_hackernews(self, client: httpx.Client, count: int = 15, min_points: int = 50) -> list:
        resp = client.get("https://hacker-news.firebaseio.com/v0/topstories.json")
        ids = resp.json()[:40]

        articles = []
        for story_id in ids:
            if len(articles) >= count:
                break
            try:
                r = client.get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json")
                item = r.json()
                if not item or item.get("type") != "story":
                    continue
                if item.get("score", 0) < min_points:
                    continue
                url = item.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
                articles.append({
                    "url": url,
                    "title": item.get("title", "").strip(),
                    "source": "Hacker News",
                    "content": f"Points: {item.get('score', 0)} | Comments: {item.get('descendants', 0)}",
                    "published_at": datetime.utcfromtimestamp(item.get("time", 0)).isoformat() if item.get("time") else None,
                })
            except Exception:
                continue
        return articles

    def _fetch_reddit(self, client: httpx.Client, subreddit: str, count: int = 8) -> list:
        resp = client.get(f"https://www.reddit.com/r/{subreddit}/hot.json?limit={count}")
        data = resp.json()
        articles = []
        for post in data.get("data", {}).get("children", []):
            d = post.get("data", {})
            title = d.get("title", "").strip()
            if not title:
                continue
            articles.append({
                "url": f"https://reddit.com{d.get('permalink', '')}",
                "title": title,
                "source": f"Reddit r/{subreddit}",
                "content": d.get("selftext", "")[:400] or f"Score: {d.get('score', 0)} | Comments: {d.get('num_comments', 0)}",
                "published_at": datetime.utcfromtimestamp(d.get("created_utc", 0)).isoformat() if d.get("created_utc") else None,
            })
        return articles

    def _fetch_github_trending(self, client: httpx.Client) -> list:
        resp = client.get("https://github.com/trending")
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "lxml")
        articles = []
        for repo in soup.select("article.Box-row")[:12]:
            try:
                h2 = repo.select_one("h2 a")
                if not h2:
                    continue
                name = h2.get_text(separator="/", strip=True).replace(" ", "")
                desc_el = repo.select_one("p")
                desc = desc_el.get_text(strip=True) if desc_el else ""
                stars_el = repo.select("a.Link--muted")
                stars = stars_el[0].get_text(strip=True) if stars_el else "?"
                lang_el = repo.select_one("span[itemprop='programmingLanguage']")
                lang = lang_el.get_text(strip=True) if lang_el else ""
                clean_name = name.replace("//", "/").strip("/")
                articles.append({
                    "url": f"https://github.com/{clean_name}",
                    "title": f"[GitHub] {clean_name} — {desc[:70]}",
                    "source": "GitHub Trending",
                    "content": f"Language: {lang} | Stars: {stars} | {desc}",
                    "published_at": datetime.utcnow().isoformat(),
                })
            except Exception:
                continue
        return articles

    def _strip_html(self, text: str) -> str:
        from bs4 import BeautifulSoup
        if not text:
            return ""
        return BeautifulSoup(text, "lxml").get_text(separator=" ").strip()

    def _decode_html(self, text: str) -> str:
        import html
        return html.unescape(text) if text else ""
