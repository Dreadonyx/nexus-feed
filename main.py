#!/usr/bin/env python3
import typer
import yaml
import time
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(
    name="nexus",
    help="NexusFeed — AI-powered tech news aggregator with chat",
    add_completion=False,
)
console = Console()


def load_config() -> dict:
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        console.print("[red]config.yaml not found.[/red]")
        raise typer.Exit(1)
    with open(config_path) as f:
        return yaml.safe_load(f)


@app.command()
def fetch(
    notify: bool = typer.Option(False, "--notify", "-n", help="Send desktop notification"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress per-article output"),
):
    """Fetch latest news from all configured sources and enrich with AI."""
    from src.database import Database
    from src.fetcher import Fetcher
    from src.ai_client import AIClient
    from src.notifier import Notifier

    config = load_config()
    db = Database()
    fetcher = Fetcher(config)
    ai = AIClient(config)

    console.print("[bold cyan]◈ Fetching news...[/bold cyan]")
    articles = fetcher.fetch_all()
    console.print(f"[dim]Found {len(articles)} articles from sources[/dim]")

    new_count = 0
    skipped = 0

    with console.status("[cyan]Enriching with AI...[/cyan]") as status:
        for i, article in enumerate(articles):
            if db.is_new(article["url"]):
                enriched = ai.enrich_article(article)
                db.save_article(enriched)
                new_count += 1
                if not quiet:
                    score = enriched.get("score", 0)
                    score_style = "green" if score >= 7 else ("yellow" if score >= 4 else "dim")
                    console.print(
                        f"  [{score_style}]{score:2d}[/{score_style}]  {article['title'][:65]}"
                        f"  [dim]{article['source']}[/dim]"
                    )
            else:
                skipped += 1
            status.update(f"[cyan]Processed {i+1}/{len(articles)} articles...[/cyan]")

    console.print(f"\n[green]✓ {new_count} new articles saved[/green]  [dim]{skipped} already seen[/dim]")

    if notify:
        Notifier().send(f"NexusFeed: {new_count} new articles", "Run: nexus digest")

    db.close()


@app.command()
def digest(
    top: int = typer.Option(15, "--top", "-t", help="Number of top articles to show"),
    topic: str = typer.Option(None, "--topic", help="Filter by topic"),
    hours: int = typer.Option(24, "--hours", "-H", help="Look back N hours"),
    export: bool = typer.Option(False, "--export", "-e", help="Export as markdown"),
):
    """Show today's AI-ranked digest of top articles."""
    from src.database import Database
    from src.ai_client import AIClient
    from src.digest import DigestGenerator

    config = load_config()
    db = Database()
    ai = AIClient(config)
    gen = DigestGenerator(config, db, ai)
    gen.show(top=top, topic=topic, export=export)
    db.close()


@app.command()
def chat():
    """Chat with your feed — ask questions grounded in your articles."""
    from src.database import Database
    from src.ai_client import AIClient
    from src.chat import ChatSession

    config = load_config()
    db = Database()
    ai = AIClient(config)
    session = ChatSession(config, db, ai)
    session.start()
    db.close()


@app.command()
def trends():
    """Show trending keywords and topics in your feed."""
    from src.database import Database
    from src.trends import TrendTracker

    config = load_config()
    db = Database()
    tracker = TrendTracker(db)
    tracker.show()
    db.close()


@app.command()
def tui():
    """Launch the interactive terminal UI."""
    from src.database import Database
    from src.tui import TUI

    config = load_config()
    db = Database()
    interface = TUI(config, db)
    interface.run()
    db.close()


@app.command()
def alerts():
    """Check for keyword alerts in recent articles."""
    from src.database import Database
    from rich.table import Table
    from rich import box

    config = load_config()
    db = Database()

    recent = db.get_recent_articles(hours=12, limit=100)
    keywords = config.get("alerts", {}).get("keywords", [])

    hits = []
    for article in recent:
        text = (article.get("title") or "") + " " + (article.get("summary") or "")
        for kw in keywords:
            if kw.lower() in text.lower():
                hits.append((kw, article))
                break

    if hits:
        table = Table(title="[bold red]Keyword Alerts[/bold red]", box=box.ROUNDED)
        table.add_column("Keyword", style="red bold", width=15)
        table.add_column("Article", style="white")
        table.add_column("Source", style="dim", width=20)
        table.add_column("Score", width=5)

        for kw, article in hits:
            table.add_row(
                kw,
                article["title"][:65],
                article["source"],
                str(article.get("score", 0))
            )
        console.print(table)
    else:
        console.print(f"[green]No alerts triggered for: {', '.join(keywords)}[/green]")

    db.close()


@app.command()
def bookmarks():
    """Show bookmarked articles."""
    from src.database import Database
    from rich.table import Table
    from rich import box

    config = load_config()
    db = Database()
    saved = db.get_bookmarks()

    if not saved:
        console.print("[yellow]No bookmarks yet. Use [bold]nexus tui[/bold] and press 'b <id>' to bookmark.[/yellow]")
        return

    table = Table(title=f"[bold yellow]Bookmarks ({len(saved)})[/bold yellow]", box=box.ROUNDED)
    table.add_column("ID", style="dim", width=4)
    table.add_column("Title", style="white", ratio=3)
    table.add_column("Source", style="dim", ratio=1)
    table.add_column("Score", width=5)

    for a in saved:
        table.add_row(
            str(a["id"]),
            a["title"][:70],
            a["source"],
            str(a.get("score", 0))
        )
    console.print(table)
    db.close()


@app.command()
def daemon(
    interval: int = typer.Option(60, "--interval", "-i", help="Fetch interval in minutes"),
):
    """Run as a background daemon, auto-fetching on a schedule."""
    from src.database import Database
    from src.fetcher import Fetcher
    from src.ai_client import AIClient
    from src.notifier import Notifier

    console.print(Panel(
        f"[bold cyan]NexusFeed Daemon[/bold cyan] — fetching every [yellow]{interval}m[/yellow]\n"
        f"[dim]Press Ctrl+C to stop[/dim]",
        border_style="cyan"
    ))

    while True:
        try:
            config = load_config()
            db = Database()
            fetcher = Fetcher(config)
            ai = AIClient(config)

            articles = fetcher.fetch_all()
            new_count = 0
            for article in articles:
                if db.is_new(article["url"]):
                    enriched = ai.enrich_article(article)
                    db.save_article(enriched)
                    new_count += 1

            if new_count > 0:
                Notifier().send(f"NexusFeed: {new_count} new articles")

            from datetime import datetime
            console.print(f"[dim]{datetime.now().strftime('%H:%M')} — {new_count} new articles[/dim]")
            db.close()

        except Exception as e:
            console.print(f"[red]Daemon error: {e}[/red]")

        time.sleep(interval * 60)


@app.command()
def stats():
    """Show feed statistics."""
    from src.database import Database
    from rich.table import Table
    from rich import box

    config = load_config()
    db = Database()

    total = db.get_article_count()
    recent_24h = db.get_recent_articles(hours=24, limit=200)
    bookmarks_list = db.get_bookmarks()
    events = db.get_events()

    # Source breakdown
    source_counts = {}
    for a in recent_24h:
        src = a.get("source", "Unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    console.print(Panel(
        f"[bold cyan]NexusFeed Stats[/bold cyan]\n\n"
        f"  Total articles: [green]{total}[/green]\n"
        f"  Last 24h: [green]{len(recent_24h)}[/green]\n"
        f"  Bookmarks: [yellow]{len(bookmarks_list)}[/yellow]\n"
        f"  Upcoming events: [cyan]{len(events)}[/cyan]",
        border_style="cyan"
    ))

    if source_counts:
        table = Table(title="Sources (last 24h)", box=box.SIMPLE)
        table.add_column("Source", style="white")
        table.add_column("Articles", style="green", justify="right")

        for src, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
            table.add_row(src, str(count))
        console.print(table)

    db.close()


if __name__ == "__main__":
    app()
