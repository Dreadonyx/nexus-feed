from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown
from rich.text import Text

console = Console()


HELP_TEXT = """
[bold cyan]NexusFeed Chat[/bold cyan] — Ask anything about your feed

Commands:
  [yellow]/search <query>[/yellow]    Search articles by keyword
  [yellow]/top[/yellow]               Show top scored articles
  [yellow]/events[/yellow]            List upcoming events
  [yellow]/clear[/yellow]             Clear chat history
  [yellow]/quit[/yellow] or [yellow]/q[/yellow]       Exit chat

Example questions:
  "What's the biggest AI news this week?"
  "Summarize all cybersecurity alerts"
  "Are there any upcoming conferences?"
  "What's trending in open source?"
"""


class ChatSession:
    def __init__(self, config: dict, db, ai):
        self.config = config
        self.db = db
        self.ai = ai

    def start(self):
        console.print(Panel(HELP_TEXT.strip(), border_style="cyan", padding=(1, 2)))

        history = self.db.get_chat_history(limit=10)
        articles = self.db.get_all_for_chat(limit=50)

        if not articles:
            console.print("[yellow]No articles in feed yet. Run [bold]nexus fetch[/bold] first.[/yellow]\n")

        console.print(f"[dim]{len(articles)} articles loaded as context[/dim]\n")

        while True:
            try:
                user_input = Prompt.ask("[bold cyan]you[/bold cyan]").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Exiting chat.[/dim]")
                break

            if not user_input:
                continue

            # Handle commands
            if user_input.lower() in ("/quit", "/q", "exit", "quit"):
                console.print("[dim]Bye.[/dim]")
                break

            elif user_input.lower() == "/clear":
                self.db.clear_chat_history()
                history = []
                console.print("[green]Chat history cleared.[/green]\n")
                continue

            elif user_input.lower().startswith("/search "):
                query = user_input[8:].strip()
                # Try full phrase first, then individual keywords
                results = self.db.search_articles(query, limit=10)
                if not results:
                    for word in query.split():
                        if len(word) > 3:
                            results = self.db.search_articles(word, limit=10)
                            if results:
                                break
                if results:
                    console.print(f"\n[bold]Found {len(results)} articles:[/bold]")
                    for a in results:
                        console.print(f"  [cyan]•[/cyan] [white]{a['title']}[/white]  [dim]{a['source']}[/dim]")
                else:
                    console.print(f"[yellow]Nothing in your feed matches '{query}'. Try fetching more articles.[/yellow]")
                console.print()
                continue

            elif user_input.lower() == "/top":
                top = self.db.get_recent_articles(hours=24, min_score=7, limit=10)
                if top:
                    console.print("\n[bold]Top articles (score ≥ 7):[/bold]")
                    for a in top:
                        console.print(f"  [green]{a['score']:2d}[/green]  [white]{a['title']}[/white]  [dim]{a['source']}[/dim]")
                else:
                    console.print("[yellow]No high-score articles yet.[/yellow]")
                console.print()
                continue

            elif user_input.lower() == "/events":
                events = self.db.get_events()
                if events:
                    console.print("\n[bold yellow]Upcoming Events:[/bold yellow]")
                    for e in events:
                        date = e.get("event_date") or "TBD"
                        console.print(f"  [yellow]{date}[/yellow]  {e['title']}  [dim]{e['source']}[/dim]")
                else:
                    console.print("[yellow]No events detected.[/yellow]")
                console.print()
                continue

            # Regular chat — check for search intent
            search_terms = self._extract_search_terms(user_input)
            if search_terms:
                context_articles = self.db.search_articles(search_terms, limit=15)
                if not context_articles:
                    context_articles = articles
            else:
                context_articles = articles

            # Save user message
            self.db.save_chat_message("user", user_input)

            # Get AI response
            console.print("[dim]thinking...[/dim]", end="\r")
            response = self.ai.chat(user_input, context_articles, history)

            # Clear "thinking" line and show response
            console.print(" " * 20, end="\r")
            console.print(Panel(
                Markdown(response),
                title="[bold green]nexus[/bold green]",
                border_style="green",
                padding=(0, 1)
            ))

            # Save to history
            self.db.save_chat_message("assistant", response)
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": response})
            console.print()

    def _extract_search_terms(self, text: str) -> str:
        # Simple heuristic: extract key nouns/topics for targeted search
        stopwords = {"what", "is", "the", "are", "there", "any", "about", "with", "for",
                     "and", "or", "in", "on", "a", "an", "me", "tell", "show", "give",
                     "latest", "news", "recent", "this", "week", "today", "best", "top"}
        words = [w.strip("?.,!") for w in text.lower().split() if len(w) > 3]
        meaningful = [w for w in words if w not in stopwords]
        return " ".join(meaningful[:3]) if meaningful else ""
