"""Entry point: start bot + scheduler."""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import SCRAPE_INTERVAL_MINUTES, BOT_TOKEN, ADMIN_ID, OPENAI_API_KEY
from database import init_db
from bot import dp, bot, router
from scheduler import hourly_news_job

from aiogram.filters import Command
from aiogram import F
from aiogram.types import Message

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@router.message(Command("force"), F.from_user.id == ADMIN_ID)
async def on_force(message: Message):
    """Manually trigger news scraping."""
    await message.reply("🔍 Запускаю поиск новостей...")
    await hourly_news_job()
    await message.reply("✅ Готово!")


async def main():
    # Validate config
    if not BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set!")
    if not ADMIN_ID:
        raise ValueError("TELEGRAM_ADMIN_ID is not set!")
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set!")

    # Init database
    await init_db()
    logger.info("Database initialized")

    # Start scheduler
    sched = AsyncIOScheduler()
    sched.add_job(
        hourly_news_job,
        trigger=IntervalTrigger(minutes=SCRAPE_INTERVAL_MINUTES),
        id="hourly_news",
        name="Hourly news scrape & rewrite",
        max_instances=1,
    )
    sched.start()
    logger.info(f"Scheduler started (every {SCRAPE_INTERVAL_MINUTES} min)")

    # Run first job immediately
    logger.info("Running initial news job...")
    asyncio.create_task(hourly_news_job())

    # Start bot polling
    logger.info("Starting bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
