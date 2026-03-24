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

Scoring rules (be strict and accurate):
- Score 9-10 ONLY if the article is LITERALLY about: an open hackathon/competition to apply to, an internship/fellowship posting, a student program (GSoC, MLH), a grant/scholarship, or a Chennai/India-specific opportunity.
- Score 7-8 for: Indian startup funding news, useful open source projects to contribute to, AI/tech breakthroughs relevant to students learning.
- Score 4-6 for: general tech news, GitHub repos, career discussions.
- Score 1-3 for: enterprise software, politics, stock market, irrelevant corporate news.

Tags must be real descriptive keywords from the article (e.g. "python", "funding", "AI", "startup"), NOT generic words like "hackathon" unless the article is literally about one.

Return ONLY valid JSON, no extra text:
{{
  "summary": "One clean sentence summarizing what this article is actually about.",
  "key_points": ["point1", "point2", "point3"],
  "score": <integer 1-10>,
  "tags": ["tag1", "tag2", "tag3"],
  "sentiment": "positive" | "negative" | "neutral",
  "is_event": true | false,
  "event_date": "YYYY-MM-DD or null",
  "student_action": "One specific action a student can take, or null if not applicable"
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

    def chat(self, message: str, articles: list, history: list, web_results: list = None) -> str:
        # Build feed context
        context_parts = []
        for i, a in enumerate(articles[:15], 1):
            summary = a.get("summary") or a.get("content", "")[:200]
            tags = ", ".join(a.get("tags", []))
            context_parts.append(
                f"[{i}] {a['title']}\nSource: {a['source']} | Tags: {tags}\n{summary}"
            )
        feed_context = "\n\n".join(context_parts) or "No articles in feed yet."

        # Build web context
        if web_results:
            web_parts = []
            for i, r in enumerate(web_results, 1):
                web_parts.append(f"[W{i}] {r.get('title', '')}\n{r.get('body', '')}\nURL: {r.get('href', '')}")
            web_context = "\n\n".join(web_parts)
        else:
            web_context = None

        if web_context:
            system_prompt = f"""You are NexusFeed's AI assistant for a student in Chennai, India.

LIVE WEB SEARCH RESULTS (use these to answer):
---
{web_context}
---

FEED CONTEXT (secondary):
---
{feed_context}
---

Rules:
- Answer using the web search results above. Be direct and specific.
- Include URLs when relevant so the user can visit them.
- Be concise. If it's an event, include: name, date, prize/stipend, how to apply.
- Do not make up anything not in the sources above."""
        else:
            system_prompt = f"""You are NexusFeed's AI assistant for a student in Chennai, India.

FEED CONTEXT:
---
{feed_context}
---

Rules:
- Answer ONLY from the feed above. Never use outside knowledge.
- If not in the feed, say exactly: "Not in your feed. Ask me to search the web for this."
- Be short and direct. Cite article titles when referencing them."""

        messages = [{"role": "system", "content": system_prompt}]
        for h in history[-6:]:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": message})

        try:
            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=messages,
                temperature=0.7,
                max_tokens=700,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"[Error] {e}"

    def needs_web_search(self, message: str, feed_answer: str) -> bool:
        """Check if the AI indicated it needs web search."""
        indicators = ["not in your feed", "try running", "search the web", "no mention", "not found"]
        return any(ind in feed_answer.lower() for ind in indicators)

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
