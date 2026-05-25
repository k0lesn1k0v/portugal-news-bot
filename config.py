import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "0"))
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Scraping
SCRAPE_INTERVAL_MINUTES = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "60"))
MAX_ARTICLES_PER_SOURCE = int(os.getenv("MAX_ARTICLES_PER_SOURCE", "10"))

# Database
DB_PATH = os.getenv("DB_PATH", "data/news.db")
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

# News sources — Portuguese media RSS feeds
NEWS_SOURCES = [
    {
        "name": "Público",
        "rss": "https://feeds.feedburner.com/PublicoRSS",
        "fallback_url": "https://www.publico.pt",
    },
    {
        "name": "Observador",
        "rss": "https://observador.pt/feed/",
        "fallback_url": "https://observador.pt",
    },
    {
        "name": "RTP Notícias",
        "rss": "https://www.rtp.pt/noticias/rss",
        "fallback_url": "https://www.rtp.pt/noticias",
    },
    {
        "name": "Jornal de Notícias",
        "rss": "https://www.jn.pt/rss",
        "fallback_url": "https://www.jn.pt",
    },
    {
        "name": "Diário de Notícias",
        "rss": "https://www.dn.pt/rss",
        "fallback_url": "https://www.dn.pt",
    },
]
