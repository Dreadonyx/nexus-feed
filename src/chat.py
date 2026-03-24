from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown
from src.search import web_search

console = Console()


HELP_TEXT = """
[bold cyan]NexusFeed Chat[/bold cyan] — Ask anything. Searches the web live if needed.

Commands:
  [yellow]/web <query>[/yellow]       Force a live web search
  [yellow]/search <query>[/yellow]    Search your local feed
  [yellow]/top[/yellow]               Show top scored articles
  [yellow]/events[/yellow]            List upcoming events
  [yellow]/clear[/yellow]             Clear chat history
  [yellow]/quit[/yellow] or [yellow]/q[/yellow]       Exit chat

Just ask naturally — web search triggers automatically when needed:
  "Any OpenAI events with prize money?"
  "Hackathons for students in India 2026"
  "Internships at Indian AI startups"
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

            elif user_input.lower().startswith("/web "):
                query = user_input[5:].strip()
                console.print("[dim]searching the web...[/dim]", end="\r")
                results = web_search(query, max_results=6)
                console.print(" " * 30, end="\r")
                if results:
                    response = self.ai.chat(query, context_articles, history, web_results=results)
                    console.print(Panel(
                        Markdown(response),
                        title="[bold green]nexus[/bold green] [dim cyan]· live search[/dim cyan]",
                        border_style="green", padding=(0, 1)
                    ))
                else:
                    console.print("[yellow]No web results found.[/yellow]")
                console.print()
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

            # Check if query needs live search (events, hackathons, etc.)
            live_keywords = ["hackathon", "internship", "fellowship", "event", "competition",
                             "contest", "prize", "apply", "ongoing", "current", "latest",
                             "openai", "google", "microsoft", "job", "hiring", "conference"]
            needs_live = any(kw in user_input.lower() for kw in live_keywords)

            if needs_live:
                console.print("[dim]searching the web...[/dim]", end="\r")
                search_query = self._build_search_query(user_input)
                results = web_search(search_query, max_results=6)
                if results:
                    response = self.ai.chat(user_input, context_articles, history, web_results=results)
                    source_label = "[bold green]nexus[/bold green] [dim cyan]· live search[/dim cyan]"
                else:
                    console.print("[dim]thinking...[/dim]", end="\r")
                    response = self.ai.chat(user_input, context_articles, history)
                    source_label = "[bold green]nexus[/bold green]"
            else:
                console.print("[dim]thinking...[/dim]", end="\r")
                response = self.ai.chat(user_input, context_articles, history)
                # Fallback to web if feed has no answer
                if self.ai.needs_web_search(user_input, response):
                    console.print("[dim]searching the web...[/dim]", end="\r")
                    results = web_search(self._build_search_query(user_input), max_results=6)
                    if results:
                        response = self.ai.chat(user_input, context_articles, history, web_results=results)
                        source_label = "[bold green]nexus[/bold green] [dim cyan]· live search[/dim cyan]"
                    else:
                        source_label = "[bold green]nexus[/bold green]"
                else:
                    source_label = "[bold green]nexus[/bold green]"

            # Show response
            console.print(" " * 30, end="\r")
            console.print(Panel(
                Markdown(response),
                title=source_label,
                border_style="green",
                padding=(0, 1)
            ))

            # Save to history
            self.db.save_chat_message("assistant", response)
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": response})
            console.print()

    def _build_search_query(self, text: str) -> str:
        """Build a focused search query, appending India/student context."""
        base = text.strip().rstrip("?")
        # Add India context for event/opportunity queries
        event_words = ["event", "hackathon", "internship", "fellowship", "competition", "prize", "contest", "apply"]
        if any(w in text.lower() for w in event_words):
            return f"{base} India students 2025 2026"
        return base

    def _extract_search_terms(self, text: str) -> str:
        # Simple heuristic: extract key nouns/topics for targeted search
        stopwords = {"what", "is", "the", "are", "there", "any", "about", "with", "for",
                     "and", "or", "in", "on", "a", "an", "me", "tell", "show", "give",
                     "latest", "news", "recent", "this", "week", "today", "best", "top"}
        words = [w.strip("?.,!") for w in text.lower().split() if len(w) > 3]
        meaningful = [w for w in words if w not in stopwords]
        return " ".join(meaningful[:3]) if meaningful else ""
