"""Rewrite news articles in Lentach-style using OpenAI API."""

import logging
from openai import AsyncOpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """Ты — автор Telegram-канала о жизни в Португалии.
Пишешь посты в стиле Лентача: коротко, дерзко, с иронией и цепляющим заголовком.

Правила:
1. Заголовок — жирный, короткий, с эмодзи, цепляющий. Может быть провокационным или ироничным.
2. Тело поста — 3-5 предложений. Суть новости простым языком, с лёгкой иронией.
3. В конце — хештеги: #Португалия и 1-2 тематических.
4. Пиши на РУССКОМ языке.
5. Используй Telegram-форматирование: **жирный**, _курсив_.
6. Не будь занудой. Представь, что рассказываешь другу в баре.
7. Если новость скучная — сделай её интересной подачей.
8. В конце добавь ссылку на источник в формате: [Источник](url)

Формат ответа — ТОЛЬКО текст поста, без пояснений."""

PICK_BEST_PROMPT = """Ты — редактор Telegram-канала о Португалии.
Из списка новостей выбери ОДНУ самую интересную для русскоязычной аудитории,
которая живёт в Португалии или интересуется ей.

Критерии:
- Актуальность и необычность
- Влияние на повседневную жизнь экспатов / иммигрантов
- Потенциал для вовлечения (комментарии, обсуждения)
- Избегай скучных бюрократических новостей, если в них нет чего-то цепляющего

Верни ТОЛЬКО номер выбранной новости (число) и ничего больше."""


async def pick_best_article(articles: list[dict]) -> int | None:
    """Use GPT to pick the most interesting article. Returns article ID."""
    if not articles:
        return None

    numbered_list = "\n".join(
        f"{i+1}. [{a['source']}] {a['title']}\n   {a['summary'][:200]}"
        for i, a in enumerate(articles)
    )

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
        logger.error(f"Failed to parse GPT pick: {e}")
    except Exception as e:
        logger.error(f"OpenAI pick error: {e}")

    # fallback: return first article
    return articles[0]["id"] if articles else None


async def rewrite_article(title: str, summary: str, url: str, source: str) -> str | None:
    """Rewrite an article in Lentach style. Returns the post text."""
    user_msg = (
        f"Источник: {source}\n"
        f"Заголовок: {title}\n"
        f"Текст: {summary}\n"
        f"Ссылка: {url}"
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
        logger.error(f"OpenAI rewrite error: {e}")
        return None
