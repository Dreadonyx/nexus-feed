import json
import re
from groq import Groq
from rich.console import Console

console = Console()


class AIClient:
    def __init__(self, config: dict):
        groq_cfg = config.get("groq", {})
        self.client = Groq(api_key=groq_cfg.get("api_key"))
        self.model = groq_cfg.get("model", "llama3-8b-8192")
        self.chat_model = groq_cfg.get("chat_model", "llama3-70b-8192")
        self.topics = config.get("topics", [])

    def enrich_article(self, article: dict) -> dict:
        title = article.get("title", "")
        content = article.get("content", "")
        topics_str = ", ".join(self.topics)

        prompt = f"""Analyze this tech news article and return a JSON object.

Title: {title}
Content: {content[:600]}

User's topics of interest: {topics_str}

Return ONLY valid JSON with these exact keys:
{{
  "summary": "2-3 sentence summary",
  "key_points": ["point1", "point2", "point3"],
  "score": <integer 1-10, relevance to user topics>,
  "tags": ["tag1", "tag2", "tag3"],
  "sentiment": "positive" | "negative" | "neutral",
  "is_event": true | false,
  "event_date": "YYYY-MM-DD or null"
}}

Score 8-10 only for major, genuinely important news. Score 1-3 for irrelevant/noise."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=400,
            )
            text = response.choices[0].message.content.strip()
            # Extract JSON from response
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                article.update({
                    "summary": data.get("summary", ""),
                    "key_points": data.get("key_points", []),
                    "score": int(data.get("score", 0)),
                    "tags": data.get("tags", []),
                    "sentiment": data.get("sentiment", "neutral"),
                    "is_event": bool(data.get("is_event", False)),
                    "event_date": data.get("event_date"),
                })
        except Exception as e:
            console.print(f"[dim red]AI enrich failed for '{title[:40]}': {e}[/dim red]")
            article.update({
                "summary": content[:200] if content else title,
                "key_points": [],
                "score": 3,
                "tags": [],
                "sentiment": "neutral",
                "is_event": False,
                "event_date": None,
            })

        return article

    def chat(self, message: str, articles: list, history: list) -> str:
        # Build context from top articles
        context_parts = []
        for i, a in enumerate(articles[:20], 1):
            summary = a.get("summary") or a.get("content", "")[:200]
            tags = ", ".join(a.get("tags", []))
            context_parts.append(
                f"[{i}] {a['title']}\nSource: {a['source']} | Score: {a.get('score', 0)} | Tags: {tags}\n{summary}"
            )
        context = "\n\n".join(context_parts)

        system_prompt = f"""You are NexusFeed's AI assistant. You help users understand and navigate their tech news feed.

You have access to the user's current news feed:
---
{context}
---

Answer questions based on this feed. Be concise and direct. When referencing articles, cite them by title.
If asked for opinions or analysis, be direct and insightful. If the question isn't about the feed, still answer helpfully."""

        messages = [{"role": "system", "content": system_prompt}]
        for h in history[-6:]:  # last 3 exchanges
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": message})

        try:
            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=messages,
                temperature=0.7,
                max_tokens=600,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"[Error] {e}"

    def generate_digest_intro(self, articles: list) -> str:
        if not articles:
            return "No articles in today's digest."

        titles = "\n".join(f"- {a['title']}" for a in articles[:10])
        prompt = f"""Give a 2-sentence overview of today's tech news based on these headlines. Be sharp and informative.

Headlines:
{titles}

Overview:"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=150,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return ""
