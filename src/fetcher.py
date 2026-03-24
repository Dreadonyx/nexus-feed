import feedparser
import httpx
from datetime import datetime
from typing import Optional
from rich.console import Console

console = Console()


class Fetcher:
    def __init__(self, config: dict):
        self.config = config
        self.sources_cfg = config.get("sources", {})

    def fetch_all(self) -> list:
        articles = []
        seen_titles = set()

        # RSS feeds
        for feed in self.sources_cfg.get("rss", []):
            try:
                fetched = self._fetch_rss(feed["url"], feed["name"])
                articles.extend(fetched)
            except Exception as e:
                console.print(f"[yellow]RSS {feed['name']}: {e}[/yellow]")

        # Hacker News
        hn_cfg = self.sources_cfg.get("hackernews", {})
        if hn_cfg.get("enabled", False):
            try:
                articles.extend(self._fetch_hackernews(
                    count=hn_cfg.get("count", 20),
                    min_points=hn_cfg.get("min_points", 50)
                ))
            except Exception as e:
                console.print(f"[yellow]HackerNews: {e}[/yellow]")

        # Reddit
        reddit_cfg = self.sources_cfg.get("reddit", {})
        if reddit_cfg.get("enabled", False):
            for sub in reddit_cfg.get("subreddits", []):
                try:
                    articles.extend(self._fetch_reddit(sub, reddit_cfg.get("count", 10)))
                except Exception as e:
                    console.print(f"[yellow]Reddit r/{sub}: {e}[/yellow]")

        # GitHub Trending
        gh_cfg = self.sources_cfg.get("github_trending", {})
        if gh_cfg.get("enabled", False):
            try:
                articles.extend(self._fetch_github_trending())
            except Exception as e:
                console.print(f"[yellow]GitHub Trending: {e}[/yellow]")

        # Dedup by title similarity
        unique = []
        for a in articles:
            title_key = a["title"].lower()[:60]
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique.append(a)

        return unique

    def _fetch_rss(self, url: str, source_name: str) -> list:
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:15]:
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
                "title": entry.get("title", ""),
                "source": source_name,
                "content": self._strip_html(content)[:1000],
                "published_at": published,
            })
        return articles

    def _fetch_hackernews(self, count: int = 20, min_points: int = 50) -> list:
        with httpx.Client(timeout=15) as client:
            resp = client.get("https://hacker-news.firebaseio.com/v0/topstories.json")
            ids = resp.json()[:50]

        articles = []
        with httpx.Client(timeout=10) as client:
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
                    url = item.get("url", f"https://news.ycombinator.com/item?id={story_id}")
                    articles.append({
                        "url": url,
                        "title": item.get("title", ""),
                        "source": "Hacker News",
                        "content": f"HN Score: {item.get('score', 0)} | Comments: {item.get('descendants', 0)}",
                        "published_at": datetime.utcfromtimestamp(item.get("time", 0)).isoformat() if item.get("time") else None,
                    })
                except Exception:
                    continue
        return articles

    def _fetch_reddit(self, subreddit: str, count: int = 10) -> list:
        headers = {"User-Agent": "nexus-feed/1.0"}
        with httpx.Client(timeout=15, headers=headers) as client:
            resp = client.get(f"https://www.reddit.com/r/{subreddit}/hot.json?limit={count}")
            data = resp.json()

        articles = []
        for post in data.get("data", {}).get("children", []):
            d = post.get("data", {})
            if d.get("is_self") and not d.get("selftext"):
                continue
            articles.append({
                "url": f"https://reddit.com{d.get('permalink', '')}",
                "title": d.get("title", ""),
                "source": f"Reddit r/{subreddit}",
                "content": d.get("selftext", "")[:500] or f"Score: {d.get('score', 0)} | Comments: {d.get('num_comments', 0)}",
                "published_at": datetime.utcfromtimestamp(d.get("created_utc", 0)).isoformat() if d.get("created_utc") else None,
            })
        return articles

    def _fetch_github_trending(self) -> list:
        headers = {"User-Agent": "nexus-feed/1.0"}
        with httpx.Client(timeout=15, headers=headers) as client:
            resp = client.get("https://github.com/trending")

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "lxml")
        articles = []

        for repo in soup.select("article.Box-row")[:15]:
            try:
                h2 = repo.select_one("h2 a")
                if not h2:
                    continue
                name = h2.get_text(strip=True).replace("\n", "").replace(" ", "")
                desc_el = repo.select_one("p")
                desc = desc_el.get_text(strip=True) if desc_el else ""
                stars_el = repo.select("a.Link--muted")
                stars = stars_el[0].get_text(strip=True) if stars_el else "?"
                lang_el = repo.select_one("span[itemprop='programmingLanguage']")
                lang = lang_el.get_text(strip=True) if lang_el else ""

                articles.append({
                    "url": f"https://github.com/{name.strip('/')}",
                    "title": f"[GitHub Trending] {name} — {desc[:80]}",
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
