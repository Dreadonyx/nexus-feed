from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich.prompt import Prompt
from rich import box
from datetime import datetime
import time

console = Console()


class TUI:
    def __init__(self, config: dict, db):
        self.config = config
        self.db = db
        self.page = 0
        self.page_size = 10
        self.filter_topic = None

    def run(self):
        console.clear()
        self._show_header()

        articles = self.db.get_recent_articles(hours=48, min_score=0, limit=50)
        trends = self.db.get_keyword_counts(days=7)
        events = self.db.get_events()
        bookmarks = self.db.get_bookmarks()

        while True:
            console.clear()
            self._show_header()
            self._render_layout(articles, trends, events, bookmarks)

            try:
                cmd = Prompt.ask(
                    "\n[dim]Commands: [n]ext [p]rev [b]ookmark <id> [f]ilter <topic> [r]efresh [q]uit[/dim]"
                ).strip().lower()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Exiting.[/dim]")
                break

            if cmd == "q":
                break
            elif cmd == "n":
                max_page = max(0, (len(articles) - 1) // self.page_size)
                self.page = min(self.page + 1, max_page)
            elif cmd == "p":
                self.page = max(0, self.page - 1)
            elif cmd.startswith("b "):
                try:
                    article_id = int(cmd.split()[1])
                    self.db.toggle_bookmark(article_id)
                    bookmarks = self.db.get_bookmarks()
                    console.print(f"[green]Bookmark toggled for ID {article_id}[/green]")
                    time.sleep(0.8)
                except (ValueError, IndexError):
                    console.print("[red]Usage: b <article_id>[/red]")
                    time.sleep(0.8)
            elif cmd.startswith("f "):
                self.filter_topic = cmd[2:].strip() or None
                articles = self.db.get_recent_articles(
                    hours=48, min_score=0, topic=self.filter_topic, limit=50
                )
                self.page = 0
            elif cmd == "f":
                self.filter_topic = None
                articles = self.db.get_recent_articles(hours=48, min_score=0, limit=50)
                self.page = 0
            elif cmd == "r":
                articles = self.db.get_recent_articles(hours=48, min_score=0, limit=50)
                trends = self.db.get_keyword_counts(days=7)
                events = self.db.get_events()
                bookmarks = self.db.get_bookmarks()
                self.page = 0

    def _show_header(self):
        now = datetime.now().strftime("%a %b %d %Y  %H:%M")
        total = self.db.get_article_count()
        filter_str = f"  [yellow]Filter: {self.filter_topic}[/yellow]" if self.filter_topic else ""
        console.print(Panel(
            f"[bold cyan]◈ NexusFeed[/bold cyan]  [dim]{now}[/dim]  [dim]DB: {total} articles[/dim]{filter_str}",
            border_style="cyan",
            padding=(0, 1)
        ))

    def _render_layout(self, articles: list, trends: dict, events: list, bookmarks: list):
        # Main article list (paginated)
        start = self.page * self.page_size
        end = start + self.page_size
        page_articles = articles[start:end]

        # Articles panel
        art_table = Table(box=box.SIMPLE, show_header=True, padding=(0, 1), expand=True)
        art_table.add_column("ID", style="dim", width=4)
        art_table.add_column("Score", width=5)
        art_table.add_column("Title", style="white", ratio=3)
        art_table.add_column("Source", style="dim", ratio=1)
        art_table.add_column("★", width=2)

        for a in page_articles:
            score = a.get("score", 0)
            score_style = "bold green" if score >= 8 else ("yellow" if score >= 5 else "dim")
            bookmark_str = "★" if a.get("bookmarked") else ""
            art_table.add_row(
                str(a.get("id", "")),
                f"[{score_style}]{score}[/{score_style}]",
                a.get("title", "")[:70],
                a.get("source", "")[:25],
                f"[yellow]{bookmark_str}[/yellow]"
            )

        total_pages = max(1, (len(articles) + self.page_size - 1) // self.page_size)
        console.print(Panel(
            art_table,
            title=f"[bold]Feed[/bold] [dim]page {self.page + 1}/{total_pages} ({len(articles)} articles)[/dim]",
            border_style="white",
        ))

        # Side panels: trending + events
        # Trends
        trend_items = sorted(trends.items(), key=lambda x: x[1], reverse=True)
        noise = {"the", "and", "for", "with", "that", "this", "are", "new", "use", "get", "not"}
        trend_items = [(k, v) for k, v in trend_items if len(k) > 2 and k not in noise and v >= 2][:8]

        trend_lines = []
        for kw, count in trend_items:
            bar = "█" * min(count, 10)
            trend_lines.append(f"[cyan]{kw:<18}[/cyan] [green]{bar}[/green] [dim]{count}[/dim]")
        trend_content = "\n".join(trend_lines) if trend_lines else "[dim]Fetch more articles[/dim]"
        console.print(Panel(trend_content, title="[bold]Trending[/bold]", border_style="magenta"))

        # Events
        if events:
            ev_lines = []
            for e in events[:5]:
                date = e.get("event_date") or "TBD"
                ev_lines.append(f"[yellow]{date}[/yellow]  {e.get('title', '')[:50]}")
            console.print(Panel("\n".join(ev_lines), title="[bold]Events[/bold]", border_style="yellow"))

        # Bookmarks count
        if bookmarks:
            bm_lines = [f"[yellow]★[/yellow]  {b.get('title', '')[:65]}" for b in bookmarks[:5]]
            suffix = f" [dim]+{len(bookmarks)-5} more[/dim]" if len(bookmarks) > 5 else ""
            console.print(Panel(
                "\n".join(bm_lines) + suffix,
                title=f"[bold]Bookmarks[/bold] [dim]({len(bookmarks)})[/dim]",
                border_style="yellow"
            ))
