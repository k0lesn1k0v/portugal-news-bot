"""Scrape news from Portuguese media RSS feeds."""

import logging
import re
from html import unescape

import aiohttp
import feedparser

from config import NEWS_SOURCES, MAX_ARTICLES_PER_SOURCE
from database import article_exists, save_article

logger = logging.getLogger(__name__)


def clean_html(raw: str) -> str:
    """Strip HTML tags and decode entities."""
    clean = re.sub(r"<[^>]+>", "", raw)
    return unescape(clean).strip()


async def fetch_feed(session: aiohttp.ClientSession, source: dict) -> list[dict]:
    """Fetch and parse one RSS feed."""
    articles = []
    try:
        async with session.get(source["rss"], timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                logger.warning(f"[{source['name']}] HTTP {resp.status}")
                return []
            text = await resp.text()
    except Exception as e:
        logger.error(f"[{source['name']}] fetch error: {e}")
        return []

    feed = feedparser.parse(text)
    for entry in feed.entries[:MAX_ARTICLES_PER_SOURCE]:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        summary = clean_html(entry.get("summary", entry.get("description", "")))

        if not title or not link:
            continue

        articles.append({
            "source": source["name"],
            "title": title,
            "url": link,
            "summary": summary[:1000],  # cap length
        })

    logger.info(f"[{source['name']}] fetched {len(articles)} articles")
    return articles


async def scrape_all_sources() -> list[dict]:
    """Scrape all configured sources and save new articles to DB."""
    new_articles = []
    async with aiohttp.ClientSession() as session:
        for source in NEWS_SOURCES:
            articles = await fetch_feed(session, source)
            for art in articles:
                if await article_exists(art["url"]):
                    continue
                art_id = await save_article(
                    url=art["url"],
                    source=art["source"],
                    title=art["title"],
                    summary=art["summary"],
                )
                if art_id:
                    art["id"] = art_id
                    new_articles.append(art)

    logger.info(f"Total new articles saved: {len(new_articles)}")
    return new_articles
