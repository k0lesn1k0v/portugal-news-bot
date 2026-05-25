"""Periodic job: scrape → pick best → rewrite → send for approval."""

import logging

from scraper import scrape_all_sources
from rewriter import pick_best_article, rewrite_article
from database import get_article, get_new_articles, save_rewritten
from bot import send_for_approval

logger = logging.getLogger(__name__)


async def hourly_news_job():
    """Main periodic task: find news, pick the best, rewrite, send for review."""
    logger.info("⏰ Starting hourly news job...")

    # 1. Scrape all sources
    new_articles = await scrape_all_sources()
    logger.info(f"Scraped {len(new_articles)} new articles")

    # 2. Get all unprocessed articles (including previously scraped)
    candidates = await get_new_articles(limit=20)
    if not candidates:
        logger.info("No new articles to process")
        return

    # 3. Let GPT pick the most interesting one
    best_id = await pick_best_article(candidates)
    if not best_id:
        logger.warning("Could not pick best article")
        return

    article = await get_article(best_id)
    if not article:
        logger.error(f"Article #{best_id} not found in DB")
        return

    logger.info(f"Picked: [{article['source']}] {article['title']}")

    # 4. Rewrite in Lentach style
    rewritten = await rewrite_article(
        title=article["title"],
        summary=article["summary"],
        url=article["url"],
        source=article["source"],
    )
    if not rewritten:
        logger.error("Failed to rewrite article")
        return

    # 5. Save and send for approval
    await save_rewritten(best_id, rewritten)
    await send_for_approval(best_id, rewritten)
    logger.info(f"Article #{best_id} sent for approval")
