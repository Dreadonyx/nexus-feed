from rich.console import Console

console = Console()


class Notifier:
    def send(self, title: str, message: str = ""):
        # Try desktop notification first
        self._desktop(title, message)
        # Always show terminal output
        self._terminal(title, message)

    def _desktop(self, title: str, message: str):
        try:
            from plyer import notification
            notification.notify(
                title=title,
                message=message or " ",
                app_name="NexusFeed",
                timeout=8,
            )
        except Exception:
            # Fallback: try libnotify directly
            try:
                import subprocess
                subprocess.run(
                    ["notify-send", title, message or " ", "--app-name=NexusFeed"],
                    check=False, capture_output=True
                )
            except Exception:
                pass

    def _terminal(self, title: str, message: str):
        console.print(f"[bold cyan]◆ {title}[/bold cyan]  [dim]{message}[/dim]")
