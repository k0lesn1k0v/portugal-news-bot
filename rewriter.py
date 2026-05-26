"""Rewrite news articles using OpenAI API."""

import logging
from openai import AsyncOpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = (
        "Ты — автор новостного Telegram-канала о Португалии для русскоязычной аудитории.\n\n"
        "Стиль: сухой, фактурный, как Mash или Baza. Ирония — только через сами факты, "
        "НЕ через твои комментарии. Никакого натужного юмора, никаких шуток, никаких эмодзи.\n\n"
        "Структура поста:\n"
        "1. Первое предложение — главный факт, самое цепляющее. Это и есть заголовок. "
        "Без кавычек, без жирного шрифта. Если есть источник — добавь — СМИ или название издания через тире в конце.\n"
        "2. Дальше — 1-3 коротких абзаца с деталями и контекстом. Каждый абзац отделён пустой строкой.\n"
        "3. Если есть конкретные цифры, имена, даты — используй их. Конкретика > обобщения.\n"
        "4. НЕ ставь хештеги.\n"
        "5. НЕ используй эмодзи.\n"
        "6. НЕ используй Markdown-форматирование (жирный, курсив).\n"
        "7. НЕ добавляй ссылку на источник в текст поста.\n"
        "8. Пиши на РУССКОМ языке.\n\n"
        "Формат ответа — ТОЛЬКО текст поста, ничего больше."
)

PICK_BEST_PROMPT = (
        "Ты — редактор Telegram-канала о Португалии для русскоязычной аудитории.\n"
        "Из списка новостей выбери ОДНУ самую интересную.\n\n"
        "Приоритеты (от высшего к низшему):\n"
        "1. Изменения законов, визовых правил, налогов — всё что влияет на мигрантов и экспатов\n"
        "2. Кринж, абсурд, курьёзы — странные и смешные случаи из жизни Португалии\n"
        "3. Криминал, драки, скандалы — всё резонансное\n"
        "4. Необычные факты и события, которые хочется переслать другу\n\n"
        "НЕ выбирай:\n"
        "- Скучные бюрократические новости без конкретного влияния на людей\n"
        "- Спорт (если это не скандал или курьёз)\n"
        "- Протокольные встречи политиков\n\n"
        "Верни ТОЛЬКО номер выбранной новости (число) и ничего больше."
)


async def pick_best_article(articles: list[dict]) -> int | None:
        """Use GPT to pick the most interesting article. Returns article ID."""
        if not articles:
                    return None

        lines = []
        for i, a in enumerate(articles):
                    lines.append(
                                    "{}. [{}] {}\n   {}".format(i + 1, a["source"], a["title"], a["summary"][:200])
                    )
                numbered_list = "\n".join(lines)

    try:
                response = await client.chat.completions.create(
                                model=OPENAI_MODEL,
                                messages=[
                                                    {"role": "system", "content": PICK_BEST_PROMPT},
                                                    {"role": "user", "content": numbered_list},
                                ],
                                temperature=0.3,
                                max_tokens=10,
                )
                choice = response.choices[0].message.content.strip()
                idx = int(choice) - 1
                if 0 <= idx < len(articles):
                                return articles[idx]["id"]
    except (ValueError, IndexError) as e:
        logger.error("Failed to parse GPT pick: %s", e)
except Exception as e:
        logger.error("OpenAI pick error: %s", e)

    return articles[0]["id"] if articles else None


async def rewrite_article(title: str, summary: str, url: str, source: str) -> str | None:
        """Rewrite an article. Returns the post text."""
    user_msg = "Источник: {}\nЗаголовок: {}\nТекст: {}\nСсылка: {}".format(
                source, title, summary, url
    )

    try:
                response = await client.chat.completions.create(
                                model=OPENAI_MODEL,
                                messages=[
                                                    {"role": "system", "content": SYSTEM_PROMPT},
                                                    {"role": "user", "content": user_msg},
                                ],
                                temperature=0.8,
                                max_tokens=500,
                )
                return response.choices[0].message.content.strip()
except Exception as e:
        logger.error("OpenAI rewrite error: %s", e)
        return None
