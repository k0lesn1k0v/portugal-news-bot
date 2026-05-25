"""SQLite database for tracking processed articles."""

import aiosqlite
from config import DB_PATH


async def init_db():
    """Create tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT,
                rewritten_text TEXT,
                status TEXT DEFAULT 'new',  -- new / pending / approved / rejected / published
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                published_at TIMESTAMP
            )
        """)
        await db.commit()


async def article_exists(url: str) -> bool:
    """Check if we already processed this article."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT 1 FROM articles WHERE url = ?", (url,))
        return await cursor.fetchone() is not None


async def save_article(url: str, source: str, title: str, summary: str) -> int | None:
    """Save a new article. Returns its ID or None if duplicate."""
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            cursor = await db.execute(
                "INSERT INTO articles (url, source, title, summary) VALUES (?, ?, ?, ?)",
                (url, source, title, summary),
            )
            await db.commit()
            return cursor.lastrowid
        except aiosqlite.IntegrityError:
            return None


async def save_rewritten(article_id: int, text: str):
    """Save the rewritten post text and mark as pending approval."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE articles SET rewritten_text = ?, status = 'pending' WHERE id = ?",
            (text, article_id),
        )
        await db.commit()


async def get_article(article_id: int) -> dict | None:
    """Get article by ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def set_status(article_id: int, status: str):
    """Update article status."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE articles SET status = ? WHERE id = ?",
            (status, article_id),
        )
        await db.commit()


async def get_new_articles(limit: int = 20) -> list[dict]:
    """Get unprocessed articles sorted by newest first."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM articles WHERE status = 'new' ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
