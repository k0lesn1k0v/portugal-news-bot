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
_waiting_photo: dict[int, int] = {}  # user_msg_id -> article_id


def approval_keyboard(article_id: int) -> InlineKeyboardMarkup:
    """Inline keyboard for approve / reject / regenerate."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Одобрить",
                callback_data=f"approve:{article_id}",
            ),
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=f"reject:{article_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔄 Перегенерировать",
                callback_data=f"regen:{article_id}",
            ),
        ],
    ])


async def send_for_approval(article_id: int, text: str):
    """Send a rewritten post to admin for approval."""
    try:
        msg = await bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📝 <b>Новый пост на согласование</b> (#{article_id})\n\n{text}",
            parse_mode=ParseMode.HTML,
            reply_markup=approval_keyboard(article_id),
        )
        logger.info(f"Sent article #{article_id} for approval")
        return msg
    except Exception as e:
        logger.error(f"Failed to send for approval: {e}")
        return None


@router.callback_query(F.data.startswith("approve:"))
async def on_approve(callback: CallbackQuery):
    """Handle approve button — ask for photo."""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return

    article_id = int(callback.data.split(":")[1])
    article = await get_article(article_id)
    if not article:
        await callback.answer("Статья не найдена")
        return

    await set_status(article_id, "approved")

    msg = await callback.message.answer(
        f"📸 Отправь картинку для поста #{article_id}.\n"
        "Или отправь /skip чтобы опубликовать без картинки."
    )
    _waiting_photo[callback.from_user.id] = article_id
    await callback.answer("✅ Одобрено! Жду картинку.")


@router.callback_query(F.data.startswith("reject:"))
async def on_reject(callback: CallbackQuery):
    """Handle reject button."""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return

    article_id = int(callback.data.split(":")[1])
    await set_status(article_id, "rejected")
    await callback.answer("❌ Отклонено")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply("❌ Пост отклонён.")


@router.callback_query(F.data.startswith("regen:"))
async def on_regenerate(callback: CallbackQuery):
    """Handle regenerate button — re-rewrite the article."""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return

    article_id = int(callback.data.split(":")[1])
    article = await get_article(article_id)
    if not article:
        await callback.answer("Статья не найдена")
        return

    await callback.answer("🔄 Перегенерирую...")
    await callback.message.edit_reply_markup(reply_markup=None)

    # Re-import here to avoid circular imports
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
        await callback.message.reply("⚠️ Не удалось перегенерировать. Попробуй ещё раз.")


@router.message(F.photo, F.from_user.id == ADMIN_ID)
async def on_photo(message: Message):
    """Receive photo and publish the post to channel."""
    article_id = _waiting_photo.pop(message.from_user.id, None)
    if article_id is None:
        return  # no pending article

    article = await get_article(article_id)
    if not article or not article.get("rewritten_text"):
        await message.reply("⚠️ Текст поста не найден.")
        return

    try:
        photo = message.photo[-1]  # highest resolution
        await bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=photo.file_id,
            caption=article["rewritten_text"],
            parse_mode=ParseMode.HTML,
        )
        await set_status(article_id, "published")
        await message.reply("🚀 Пост опубликован в канале!")
        logger.info(f"Article #{article_id} published with photo")
    except Exception as e:
        logger.error(f"Publish error: {e}")
        await message.reply(f"⚠️ Ошибка публикации: {e}")


@router.message(Command("skip"), F.from_user.id == ADMIN_ID)
async def on_skip_photo(message: Message):
    """Publish without a photo."""
    article_id = _waiting_photo.pop(message.from_user.id, None)
    if article_id is None:
        await message.reply("Нет поста, ожидающего картинку.")
        return

    article = await get_article(article_id)
    if not article or not article.get("rewritten_text"):
        await message.reply("⚠️ Текст поста не найден.")
        return

    try:
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=article["rewritten_text"],
            parse_mode=ParseMode.HTML,
        )
        await set_status(article_id, "published")
        await message.reply("🚀 Пост опубликован в канале (без картинки)!")
        logger.info(f"Article #{article_id} published without photo")
    except Exception as e:
        logger.error(f"Publish error: {e}")
        await message.reply(f"⚠️ Ошибка публикации: {e}")


@router.message(Command("start"), F.from_user.id == ADMIN_ID)
async def on_start(message: Message):
    await message.reply(
        "👋 Привет! Я бот для публикации новостей о Португалии.\n\n"
        "Каждый час я нахожу интересную новость, переписываю её "
        "в стиле Лентача и присылаю тебе на согласование.\n\n"
        "Команды:\n"
        "/status — текущий статус\n"
        "/force — принудительно запустить поиск новостей\n"
        "/skip — опубликовать без картинки (после одобрения)"
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
        await message.reply("📊 Пока нет статей в базе.")
        return

    stats = "\n".join(f"  {status}: {count}" for status, count in rows)
    await message.reply(f"📊 <b>Статистика:</b>\n{stats}", parse_mode=ParseMode.HTML)
