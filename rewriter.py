"""Rewrite news articles using OpenAI API."""

import logging
from openai import AsyncOpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = (
    "Ty - avtor novostnogo Telegram-kanala o Portugalii dlya russkoyazychnoj auditorii.\n\n"
    "Stil: suhoj, fakturnyj, kak Mash ili Baza. Ironiya - tolko cherez sami fakty, "
    "NE cherez tvoi kommentarii. Nikakogo natuznogo yumora, nikakikh shutok, nikakikh emodzi.\n\n"
    "Struktura posta:\n"
    "1. Pervoe predlozhenie - glavnyj fakt, samoe ceplyayushee. Eto i est zagolovok. "
    "Bez kavychek, bez zhirnogo shrifta. Esli est istochnik - dobav - SMI ili nazvanie izdaniya cherez tire v konce.\n"
    "2. Dalshe - 1-3 korotkih abzaca s detalyami i kontekstom. Kazhdyj abzac otdelen pustoj strokoj.\n"
    "3. Esli est konkretnye cifry, imena, daty - ispolzuj ih. Konkretika > obobsheniya.\n"
    "4. NE stav heshtegi.\n"
    "5. NE ispolzuj emodzi.\n"
    "6. NE ispolzuj Markdown-formatirovanie (zhirnyj, kursiv).\n"
    "7. NE dobavlyaj ssylku na istochnik v tekst posta.\n"
    "8. Pishi na RUSSKOM yazyke.\n\n"
    "Format otveta - TOLKO tekst posta, nichego bolshe."
)

PICK_BEST_PROMPT = (
    "Ty - redaktor Telegram-kanala o Portugalii dlya russkoyazychnoj auditorii.\n"
    "Iz spiska novostej vyberi ODNU samuyu interesnuyu.\n\n"
    "Prioritety (ot vysshego k nizshemu):\n"
    "1. Izmeneniya zakonov, vizovyh pravil, nalogov - vsyo chto vliyaet na migrantov i ekspatov\n"
    "2. Krinzh, absurd, kuryozy - strannye i smeshnye sluchai iz zhizni Portugalii\n"
    "3. Kriminal, draki, skandaly - vsyo rezonansnoe\n"
    "4. Neobychnye fakty i sobytiya, kotorye hochetsya pereslat drugu\n\n"
    "NE vybiraj:\n"
    "- Skuchnye byurokraticheskie novosti bez konkretnogo vliyaniya na lyudej\n"
    "- Sport (esli eto ne skandal ili kuryoz)\n"
    "- Protokolnye vstrechi politikov\n\n"
    "Verni TOLKO nomer vybrannoj novosti (chislo) i nichego bolshe."
)


async def pick_best_article(articles):
    """Use GPT to pick the most interesting article. Returns article ID."""
    if not articles:
        return None

    lines = []
    for i, a in enumerate(articles):
        line = "{}. [{}] {}  {}".format(i + 1, a["source"], a["title"], a["summary"][:200])
        lines.append(line)
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


async def rewrite_article(title, summary, url, source):
    """Rewrite an article. Returns the post text."""
    user_msg = "Istochnik: {}\nZagolovok: {}\nTekst: {}\nSsylka: {}".format(
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
