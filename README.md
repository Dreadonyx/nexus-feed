# nexus-feed 📡

> Tech news aggregator for the terminal. Fetch, summarize, and actually talk to your feed.

I got tired of opening 10 tabs to stay updated. nexus-feed pulls from RSS, Hacker News, Reddit, and GitHub Trending — scores everything by relevance, and lets you chat with your feed like it's a person.

## Features

- Multi-source fetching — RSS, Hacker News, Reddit, GitHub Trending
- AI enrichment — Groq summarizes articles, scores relevance 1–10, extracts tags and sentiment
- Chat mode — ask "what's the biggest AI news this week?" and get answers from your actual fetched articles
- Trend radar — see which topics are spiking vs last week
- Event detection — auto-flags conferences, launches, deadlines
- Keyword alerts — instant flag when CVEs, breaches, or custom keywords appear
- Bookmarks + markdown digest export
- Rich interactive TUI
- Daemon mode with desktop notifications

## Setup

```bash
git clone https://github.com/Dreadonyx/nexus-feed
cd nexus-feed
pip install -r requirements.txt
# add your Groq API key to config.yaml
python main.py fetch
```

## Usage

```bash
python main.py fetch       # pull and enrich articles
python main.py digest      # today's ranked digest
python main.py chat        # chat with your feed
python main.py trends      # what's spiking this week
python main.py tui         # interactive mode
python main.py alerts      # keyword alerts
python main.py bookmarks   # saved articles
python main.py stats       # feed stats
python main.py daemon --interval 60  # run in background
```

## Config

Edit `config.yaml` to set:
- **topics** — what you care about (used for relevance scoring)
- **sources** — RSS feeds, toggle HN / Reddit / GitHub Trending
- **alerts.keywords** — words that trigger immediate alerts
- **digest.min_score** — minimum AI score to appear in digest (1–10)

## Stack

- Groq API (LLaMA3-8b for enrichment, LLaMA3-70b for chat)
- feedparser, httpx, BeautifulSoup
- Rich + Typer
- SQLite
