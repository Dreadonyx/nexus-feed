from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich import box
from rich.text import Text
from typing import Optional

console = Console()


class DigestGenerator:
    def __init__(self, config: dict, db, ai=None):
        self.config = config
        self.db = db
        self.ai = ai
        self.digest_cfg = config.get("digest", {})

    def show(self, top: int = 15, topic: Optional[str] = None, export: bool = False):
        min_score = self.digest_cfg.get("min_score", 5)
        articles = self.db.get_recent_articles(hours=24, min_score=min_score, topic=topic, limit=top)

        if not articles:
            console.print(Panel(
                "[yellow]No articles found. Run [bold]nexus fetch[/bold] first.[/yellow]",
                title="NexusFeed Digest",
                border_style="yellow"
            ))
            return

        # Header
        date_str = datetime.now().strftime("%A, %B %d %Y")
        header = f"[bold cyan]NexusFeed[/bold cyan] [dim]—[/dim] [white]{date_str}[/white]"
        if topic:
            header += f"  [dim]Topic: {topic}[/dim]"
        console.print(Panel(header, border_style="cyan", padding=(0, 1)))

        # AI intro
        if self.ai:
            intro = self.ai.generate_digest_intro(articles)
            if intro:
                console.print(f"\n[italic dim]{intro}[/italic dim]\n")

        # Group by topic if configured
        if self.digest_cfg.get("group_by_topic") and not topic:
            self._show_grouped(articles)
        else:
            self._show_flat(articles)

        # Events
        events = self.db.get_events()
        if events:
            self._show_events(events)

        # Stats footer
        total = self.db.get_article_count()
        console.print(f"\n[dim]Database: {total} total articles | Showing top {len(articles)} from last 24h[/dim]")

        if export:
            path = self._export_markdown(articles, events)
            console.print(f"\n[green]Exported to {path}[/green]")

    def _show_flat(self, articles: list):
        for i, a in enumerate(articles, 1):
            self._render_article(i, a)

    def _show_grouped(self, articles: list):
        groups = {}
        ungrouped = []

        for a in articles:
            tags = a.get("tags", [])
            placed = False
            for topic in self.config.get("topics", []):
                if any(topic.lower() in t.lower() for t in tags) or topic.lower() in (a.get("title") or "").lower():
                    groups.setdefault(topic, []).append(a)
                    placed = True
                    break
            if not placed:
                ungrouped.append(a)

        for topic, group_articles in groups.items():
            console.print(f"\n[bold magenta]◆ {topic.upper()}[/bold magenta]")
            for i, a in enumerate(group_articles, 1):
                self._render_article(i, a, compact=True)

        if ungrouped:
            console.print(f"\n[bold dim]◆ OTHER[/bold dim]")
            for i, a in enumerate(ungrouped, 1):
                self._render_article(i, a, compact=True)

    def _render_article(self, idx: int, article: dict, compact: bool = False):
        score = article.get("score", 0)
        sentiment = article.get("sentiment", "neutral")
        title = article.get("title", "Untitled")
        source = article.get("source", "")
        url = article.get("url", "")
        summary = article.get("summary", "")
        key_points = article.get("key_points", [])
        tags = article.get("tags", [])
        bookmarked = article.get("bookmarked", 0)

        # Score color
        if score >= 8:
            score_style = "bold green"
        elif score >= 5:
            score_style = "yellow"
        else:
            score_style = "dim"

        # Sentiment icon
        sent_icon = {"positive": "▲", "negative": "▼", "neutral": "●"}.get(sentiment, "●")
        sent_color = {"positive": "green", "negative": "red", "neutral": "dim"}.get(sentiment, "dim")

        bookmark_str = " [yellow]★[/yellow]" if bookmarked else ""
        article_id = article.get("id", "")

        title_line = f"[{score_style}]{score:2d}[/{score_style}] [{sent_color}]{sent_icon}[/{sent_color}]{bookmark_str}  [bold white]{title}[/bold white]"
        meta_line = f"     [dim]{source}[/dim]  [blue][link={url}]{url[:60]}[/link][/blue]"

        console.print(title_line)
        console.print(meta_line)

        if not compact:
            if summary:
                console.print(f"     [dim]{summary}[/dim]")
            if key_points:
                for point in key_points[:2]:
                    console.print(f"     [dim cyan]• {point}[/dim cyan]")
            if tags:
                tag_str = "  ".join(f"[dim magenta]#{t}[/dim magenta]" for t in tags[:5])
                console.print(f"     {tag_str}")
        else:
            if summary:
                console.print(f"     [dim]{summary[:120]}[/dim]")

        console.print(f"     [dim]ID: {article_id}[/dim]")
        console.print()

    def _show_events(self, events: list):
        console.print("[bold yellow]◆ UPCOMING EVENTS[/bold yellow]")
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        table.add_column("Date", style="yellow", width=12)
        table.add_column("Event", style="white")
        table.add_column("Source", style="dim", width=20)

        for e in events[:8]:
            date = e.get("event_date") or "TBD"
            table.add_row(date, e.get("title", "")[:70], e.get("source", ""))

        console.print(table)

    def _export_markdown(self, articles: list, events: list) -> Path:
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_dir = Path(__file__).parent.parent / "digests"
        output_dir.mkdir(exist_ok=True)
        path = output_dir / f"digest-{date_str}.md"

        lines = [f"# NexusFeed Digest — {date_str}\n"]
        for a in articles:
            lines.append(f"## {a['title']}\n")
            lines.append(f"**Source:** {a['source']} | **Score:** {a.get('score', 0)}\n")
            lines.append(f"**URL:** {a.get('url', '')}\n")
            if a.get("summary"):
                lines.append(f"\n{a['summary']}\n")
            if a.get("key_points"):
                for p in a["key_points"]:
                    lines.append(f"- {p}\n")
            lines.append("\n---\n")

        if events:
            lines.append("## Upcoming Events\n")
            for e in events:
                lines.append(f"- **{e.get('event_date', 'TBD')}** — {e.get('title', '')}\n")

        path.write_text("".join(lines))
        return path
