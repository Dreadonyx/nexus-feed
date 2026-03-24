from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()


class TrendTracker:
    def __init__(self, db):
        self.db = db

    def show(self):
        # This week vs last week
        this_week = self.db.get_keyword_counts(days=7)
        last_week = self.db.get_keyword_counts_period(days_start=14, days_end=7)

        if not this_week:
            console.print(Panel(
                "[yellow]Not enough data yet. Fetch more articles to see trends.[/yellow]",
                title="Trend Radar",
                border_style="yellow"
            ))
            return

        # Filter noise: skip single-char, numbers, common words
        noise = {"the", "and", "for", "with", "that", "this", "from", "have", "not",
                 "are", "was", "but", "you", "all", "can", "has", "its", "new",
                 "will", "one", "how", "what", "more", "use", "get"}

        filtered = {
            k: v for k, v in this_week.items()
            if len(k) > 2 and k not in noise and not k.isdigit() and v >= 2
        }

        # Sort by count
        sorted_keywords = sorted(filtered.items(), key=lambda x: x[1], reverse=True)

        # Calculate trend direction
        trending_up = []
        trending_down = []
        stable = []

        for kw, count in sorted_keywords[:30]:
            prev = last_week.get(kw, 0)
            if prev == 0:
                delta_pct = 100
            else:
                delta_pct = ((count - prev) / prev) * 100

            if delta_pct >= 20:
                trending_up.append((kw, count, delta_pct))
            elif delta_pct <= -20:
                trending_down.append((kw, count, delta_pct))
            else:
                stable.append((kw, count, delta_pct))

        console.print(Panel(
            "[bold cyan]NexusFeed[/bold cyan] — Keyword Trend Radar (last 7 days)",
            border_style="cyan"
        ))

        # Trending up
        if trending_up:
            table = Table(title="[bold green]Trending Up ▲[/bold green]", box=box.SIMPLE, padding=(0, 2))
            table.add_column("Keyword", style="white", min_width=20)
            table.add_column("Count", style="green", justify="right")
            table.add_column("Change", style="green", justify="right")

            for kw, count, delta in trending_up[:15]:
                delta_str = f"+{delta:.0f}%" if delta < 1000 else "NEW"
                table.add_row(kw, str(count), delta_str)
            console.print(table)

        # Stable
        if stable:
            table = Table(title="[bold yellow]Stable ●[/bold yellow]", box=box.SIMPLE, padding=(0, 2))
            table.add_column("Keyword", style="white", min_width=20)
            table.add_column("Count", style="yellow", justify="right")
            table.add_column("Change", style="dim", justify="right")

            for kw, count, delta in stable[:10]:
                delta_str = f"{delta:+.0f}%"
                table.add_row(kw, str(count), delta_str)
            console.print(table)

        # Trending down
        if trending_down:
            table = Table(title="[bold red]Fading ▼[/bold red]", box=box.SIMPLE, padding=(0, 2))
            table.add_column("Keyword", style="dim", min_width=20)
            table.add_column("Count", style="red", justify="right")
            table.add_column("Change", style="red", justify="right")

            for kw, count, delta in trending_down[:5]:
                table.add_row(kw, str(count), f"{delta:.0f}%")
            console.print(table)

        if not trending_up and not stable and not trending_down:
            console.print("[dim]Fetch more articles over time to see trend comparisons.[/dim]")
