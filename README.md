# NexusFeed

AI-powered tech news aggregator for the terminal. Fetches from RSS, Hacker News, Reddit, and GitHub Trending — summarizes with Groq, scores by relevance, and lets you **chat with your feed**.

## Features

- **Multi-source fetching** — RSS feeds, Hacker News, Reddit, GitHub Trending
- **AI enrichment** — Groq (LLaMA3) summarizes articles, scores relevance 1-10, extracts tags and sentiment
- **Chat with your feed** — Ask "what's the biggest AI news this week?" and get answers from your actual articles
- **Trend radar** — See which topics are spiking vs last week
- **Event detection** — Auto-detects conferences, launches, deadlines in articles
- **Smart dedup** — Same story from multiple sources shown once
- **Keyword alerts** — Instant flag when CVEs, breaches, or your custom keywords appear
- **Bookmarks** — Save articles to read later
- **Export digest** — Save daily digest as markdown
- **Rich TUI** — Interactive terminal UI with navigation
- **Daemon mode** — Runs on a schedule, sends desktop notifications

## Setup

```bash
git clone https://github.com/Dreadonyx/nexus-feed
cd nexus-feed
pip install -r requirements.txt
```

Edit `config.yaml` and add your Groq API key (get one free at console.groq.com).

## Usage

```bash
# Fetch latest news and enrich with AI
python main.py fetch

# Show today's ranked digest
python main.py digest

# Chat with your feed
python main.py chat

# Trend radar
python main.py trends

# Interactive TUI
python main.py tui

# Keyword alerts
python main.py alerts

# Bookmarks
python main.py bookmarks

# Stats
python main.py stats

# Run as daemon (fetches every 60 minutes)
python main.py daemon --interval 60
```

## Config

Edit `config.yaml` to customize:
- **topics** — what you care about (used for relevance scoring)
- **sources** — RSS feeds, enable/disable HN, Reddit, GitHub Trending
- **alerts.keywords** — words that trigger immediate alerts
- **digest.min_score** — minimum AI score to show in digest (1-10)

## Stack

- **Groq API** (LLaMA3-8b for enrichment, LLaMA3-70b for chat)
- **feedparser** — RSS parsing
- **httpx** — HTTP client
- **Rich + Typer** — Terminal UI and CLI
- **SQLite** — Local article storage
- **BeautifulSoup** — HTML parsing
