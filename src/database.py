import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional


DB_PATH = Path(__file__).parent.parent / "data" / "nexus.db"


class Database:
    def __init__(self):
        DB_PATH.parent.mkdir(exist_ok=True)
        self.conn = sqlite3.connect(str(DB_PATH))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                title TEXT,
                source TEXT,
                content TEXT,
                summary TEXT,
                key_points TEXT,
                score INTEGER DEFAULT 0,
                tags TEXT,
                sentiment TEXT,
                is_event INTEGER DEFAULT 0,
                event_date TEXT,
                student_action TEXT,
                published_at TEXT,
                fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
                bookmarked INTEGER DEFAULT 0,
                read_later INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT,
                content TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_articles_score ON articles(score DESC);
            CREATE INDEX IF NOT EXISTS idx_articles_fetched ON articles(fetched_at DESC);
            CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);
        """)
        self.conn.commit()

    def is_new(self, url: str) -> bool:
        row = self.conn.execute("SELECT id FROM articles WHERE url = ?", (url,)).fetchone()
        return row is None

    def save_article(self, article: dict):
        self.conn.execute("""
            INSERT OR IGNORE INTO articles
            (url, title, source, content, summary, key_points, score, tags, sentiment,
             is_event, event_date, student_action, published_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            article.get("url"),
            article.get("title"),
            article.get("source"),
            article.get("content", ""),
            article.get("summary", ""),
            json.dumps(article.get("key_points", [])),
            article.get("score", 0),
            json.dumps(article.get("tags", [])),
            article.get("sentiment", "neutral"),
            int(article.get("is_event", False)),
            article.get("event_date"),
            article.get("student_action"),
            article.get("published_at"),
        ))
        self.conn.commit()

    def get_recent_articles(self, hours: int = 24, min_score: int = 0, topic: Optional[str] = None, limit: int = 100) -> list:
        since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        rows = self.conn.execute("""
            SELECT * FROM articles
            WHERE fetched_at >= ? AND score >= ?
            ORDER BY score DESC, fetched_at DESC
            LIMIT ?
        """, (since, min_score, limit)).fetchall()

        articles = [dict(r) for r in rows]
        for a in articles:
            a["key_points"] = json.loads(a.get("key_points") or "[]")
            a["tags"] = json.loads(a.get("tags") or "[]")

        if topic:
            topic_lower = topic.lower()
            articles = [
                a for a in articles
                if topic_lower in (a.get("title") or "").lower()
                or topic_lower in (a.get("summary") or "").lower()
                or any(topic_lower in t.lower() for t in a.get("tags", []))
            ]
        return articles

    def get_all_for_chat(self, limit: int = 50) -> list:
        rows = self.conn.execute("""
            SELECT * FROM articles ORDER BY score DESC, fetched_at DESC LIMIT ?
        """, (limit,)).fetchall()
        articles = [dict(r) for r in rows]
        for a in articles:
            a["key_points"] = json.loads(a.get("key_points") or "[]")
            a["tags"] = json.loads(a.get("tags") or "[]")
        return articles

    def search_articles(self, query: str, limit: int = 20) -> list:
        q = f"%{query}%"
        rows = self.conn.execute("""
            SELECT * FROM articles
            WHERE title LIKE ? OR summary LIKE ? OR tags LIKE ?
            ORDER BY score DESC LIMIT ?
        """, (q, q, q, limit)).fetchall()
        articles = [dict(r) for r in rows]
        for a in articles:
            a["key_points"] = json.loads(a.get("key_points") or "[]")
            a["tags"] = json.loads(a.get("tags") or "[]")
        return articles

    def get_bookmarks(self) -> list:
        rows = self.conn.execute("""
            SELECT * FROM articles WHERE bookmarked = 1 ORDER BY fetched_at DESC
        """).fetchall()
        articles = [dict(r) for r in rows]
        for a in articles:
            a["key_points"] = json.loads(a.get("key_points") or "[]")
            a["tags"] = json.loads(a.get("tags") or "[]")
        return articles

    def toggle_bookmark(self, article_id: int):
        self.conn.execute("""
            UPDATE articles SET bookmarked = NOT bookmarked WHERE id = ?
        """, (article_id,))
        self.conn.commit()

    def get_events(self, days_ahead: int = 14) -> list:
        rows = self.conn.execute("""
            SELECT * FROM articles WHERE is_event = 1
            ORDER BY event_date ASC LIMIT 20
        """).fetchall()
        return [dict(r) for r in rows]

    def get_keyword_counts(self, days: int = 7) -> dict:
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        rows = self.conn.execute("""
            SELECT tags FROM articles WHERE fetched_at >= ?
        """, (since,)).fetchall()
        counts = {}
        for row in rows:
            tags = json.loads(row["tags"] or "[]")
            for tag in tags:
                tag = tag.lower().strip()
                if tag:
                    counts[tag] = counts.get(tag, 0) + 1
        return counts

    def get_keyword_counts_period(self, days_start: int, days_end: int) -> dict:
        since = (datetime.utcnow() - timedelta(days=days_start)).isoformat()
        until = (datetime.utcnow() - timedelta(days=days_end)).isoformat()
        rows = self.conn.execute("""
            SELECT tags FROM articles WHERE fetched_at >= ? AND fetched_at < ?
        """, (since, until)).fetchall()
        counts = {}
        for row in rows:
            tags = json.loads(row["tags"] or "[]")
            for tag in tags:
                tag = tag.lower().strip()
                if tag:
                    counts[tag] = counts.get(tag, 0) + 1
        return counts

    def get_article_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]

    def save_chat_message(self, role: str, content: str):
        self.conn.execute(
            "INSERT INTO chat_history (role, content) VALUES (?, ?)", (role, content)
        )
        self.conn.commit()

    def get_chat_history(self, limit: int = 20) -> list:
        rows = self.conn.execute("""
            SELECT role, content FROM chat_history
            ORDER BY timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in reversed(rows)]

    def clear_chat_history(self):
        self.conn.execute("DELETE FROM chat_history")
        self.conn.commit()

    def close(self):
        self.conn.close()
