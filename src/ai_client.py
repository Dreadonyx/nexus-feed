import json
import re
from groq import Groq
from rich.console import Console

console = Console()


class AIClient:
    def __init__(self, config: dict):
        groq_cfg = config.get("groq", {})
        self.client = Groq(api_key=groq_cfg.get("api_key"))
        self.model = groq_cfg.get("model", "llama-3.1-8b-instant")
        self.chat_model = groq_cfg.get("chat_model", "llama-3.3-70b-versatile")
        self.topics = config.get("topics", [])
        self.config = config

    def enrich_article(self, article: dict) -> dict:
        title = article.get("title", "")
        content = article.get("content", "")
        topics_str = ", ".join(self.topics)

        profile = self.config.get("profile", {})
        location = profile.get("location", "India")
        user_type = profile.get("type", "student")

        prompt = f"""Analyze this tech news article for a {user_type} based in {location}.

Title: {title}
Content: {content[:600]}

Topics of interest: {topics_str}

Score 9-10 for: hackathons, internships, fellowships, open source programs (GSoC, MLH), student competitions, startup funding news, job/opportunity announcements, India/Chennai-specific tech news.
Score 6-8 for: new tools/frameworks students can use, startup launches, AI breakthroughs, open source project launches.
Score 3-5 for: general tech news with some relevance.
Score 1-2 for: enterprise/corporate news, politics, stock markets, irrelevant noise.

Return ONLY valid JSON:
{{
  "summary": "1-2 sentence summary, mention if students can participate or apply",
  "key_points": ["point1", "point2", "point3"],
  "score": <integer 1-10>,
  "tags": ["tag1", "tag2", "tag3"],
  "sentiment": "positive" | "negative" | "neutral",
  "is_event": true | false,
  "event_date": "YYYY-MM-DD or null",
  "student_action": "short action if student can do something, else null"
}}"""

        try:
            import time
            for attempt in range(3):
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.2,
                        max_tokens=400,
                    )
                    break
                except Exception as e:
                    if "rate_limit" in str(e).lower() and attempt < 2:
                        time.sleep(4)
                        continue
                    raise
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
                    "student_action": data.get("student_action"),
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

        system_prompt = f"""You are NexusFeed's AI assistant. Answer ONLY based on the articles in the user's feed below.

FEED CONTEXT:
---
{context}
---

Rules:
- ONLY use information from the feed above. Never use outside knowledge or make things up.
- If the answer isn't in the feed, say: "Not in your current feed. Try running 'nexus fetch' to get more articles."
- Be short and direct. No bullet lists unless there are 3+ items.
- Cite article titles when referencing them.
- For event questions: only list events explicitly mentioned in the feed."""

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
