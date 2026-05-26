"""Telegram bot with approval workflow."""

import logging
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import Command
from aiogram.enums import ParseMode

from config import BOT_TOKEN, ADMIN_ID, CHANNEL_ID
from database import get_article, set_status

logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Track articles waiting for a photo
_waiting_photo: dict[int, int] = {}  # user_id -> article_id


def approval_keyboard(article_id: int) -> InlineKeyboardMarkup:
        """Inline keyboard for approve / reject / regenerate."""
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Approve",
                    callback_data="approve:{}".format(article_id),
                ),
                InlineKeyboardButton(
                    text="Reject",
                    callback_data="reject:{}".format(article_id),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Regenerate",
                    callback_data="regen:{}".format(article_id),
                ),
            ],
        ])


async def send_for_approval(article_id: int, text: str):
        """Send a rewritten post to admin for approval."""
        try:
                    msg = await bot.send_message(
                                    chat_id=ADMIN_ID,
                                    text="New post #{}:\n\n{}".format(article_id, text),
                                    reply_markup=approval_keyboard(article_id),
                    )
                    logger.info("Sent article #%d for approval", article_id)
                    return msg
except Exception as e:
        logger.error("Failed to send for approval: %s", e)
        return None


@router.callback_query(F.data.startswith("approve:"))
async def on_approve(callback: CallbackQuery):
        """Handle approve button — ask for photo."""
        if callback.from_user.id != ADMIN_ID:
                    await callback.answer("No access")
                    return

        article_id = int(callback.data.split(":")[1])
        article = await get_article(article_id)
        if not article:
                    await callback.answer("Article not found")
                    return

        await set_status(article_id, "approved")

    await callback.message.answer(
                "Send a photo for post #{}.\nOr send /skip to publish without a photo.".format(article_id)
    )
    _waiting_photo[callback.from_user.id] = article_id
    await callback.answer("Approved! Waiting for photo.")


@router.callback_query(F.data.startswith("reject:"))
async def on_reject(callback: CallbackQuery):
        """Handle reject button."""
        if callback.from_user.id != ADMIN_ID:
                    await callback.answer("No access")
                    return

        article_id = int(callback.data.split(":")[1])
        await set_status(article_id, "rejected")
        await callback.answer("Rejected")
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.reply("Post rejected.")


@router.callback_query(F.data.startswith("regen:"))
async def on_regenerate(callback: CallbackQuery):
        """Handle regenerate button — re-rewrite the article."""
        if callback.from_user.id != ADMIN_ID:
                    await callback.answer("No access")
                    return

        article_id = int(callback.data.split(":")[1])
        article = await get_article(article_id)
        if not article:
                    await callback.answer("Article not found")
                    return

        await callback.answer("Regenerating...")
        await callback.message.edit_reply_markup(reply_markup=None)

    from rewriter import rewrite_article
    from database import save_rewritten

    new_text = await rewrite_article(
                title=article["title"],
                summary=article["summary"],
                url=article["url"],
                source=article["source"],
    )
    if new_text:
                await save_rewritten(article_id, new_text)
                await send_for_approval(article_id, new_text)
else:
            await callback.message.reply("Failed to regenerate. Try again.")


@router.message(F.photo, F.from_user.id == ADMIN_ID)
async def on_photo(message: Message):
        """Receive photo and publish the post to channel."""
        article_id = _waiting_photo.pop(message.from_user.id, None)
        if article_id is None:
                    return

        article = await get_article(article_id)
        if not article or not article.get("rewritten_text"):
                    await message.reply("Post text not found.")
                    return

        try:
                    photo = message.photo[-1]
                    await bot.send_photo(
                        chat_id=CHANNEL_ID,
                        photo=photo.file_id,
                        caption=article["rewritten_text"],
                    )
                    if article.get("url"):
                                    await bot.send_message(
                                                        chat_id=CHANNEL_ID,
                                                        text='<a href="{}">Источник</a>'.format(article["url"]),
                                                        parse_mode=ParseMode.HTML,
                                                        disable_web_page_preview=True,
                                    )
                                await set_status(article_id, "published")
                    await message.reply("Published!")
                    logger.info("Article #%d published with photo", article_id)
except Exception as e:
        logger.error("Publish error: %s", e)
        await message.reply("Publish error: {}".format(e))


@router.message(Command("skip"), F.from_user.id == ADMIN_ID)
async def on_skip_photo(message: Message):
        """Publish without a photo."""
        article_id = _waiting_photo.pop(message.from_user.id, None)
        if article_id is None:
                    await message.reply("No post waiting for a photo.")
                    return

        article = await get_article(article_id)
        if not article or not article.get("rewritten_text"):
                    await message.reply("Post text not found.")
                    return

        try:
                    await bot.send_message(
                                    chat_id=CHANNEL_ID,
                                    text=article["rewritten_text"],
                    )
                    if article.get("url"):
                                    await bot.send_message(
                                                        chat_id=CHANNEL_ID,
                                                        text='<a href="{}">Источник</a>'.format(article["url"]),
                                                        parse_mode=ParseMode.HTML,
                                                        disable_web_page_preview=True,
                                    )
                                await set_status(article_id, "published")
                    await message.reply("Published (no photo)!")
                    logger.info("Article #%d published without photo", article_id)
except Exception as e:
        logger.error("Publish error: %s", e)
        await message.reply("Publish error: {}".format(e))


@router.message(Command("start"), F.from_user.id == ADMIN_ID)
async def on_start(message: Message):
        await message.reply(
                    "Portugal News Bot\n\n"
                    "Commands:\n"
                    "/status - stats\n"
                    "/force - run news search now\n"
                    "/skip - publish without photo"
        )


@router.message(Command("status"), F.from_user.id == ADMIN_ID)
async def on_status(message: Message):
        import aiosqlite
        from config import DB_PATH

    async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute(
                                "SELECT status, COUNT(*) FROM articles GROUP BY status"
                )
                rows = await cursor.fetchall()

    if not rows:
                await message.reply("No articles yet.")
                return

    stats = "\n".join("  {}: {}".format(status, count) for status, count in rows)
    await message.reply("Stats:\n{}".format(stats))
