# kev_filter.py
"""
Клиент для локального Kev-сервера.
Классифицирует входящие сообщения из Telegram.
Категории читаются из categories.json — можно добавлять свои.
Настройки читаются из .env.
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
CATEGORIES_FILE = BASE_DIR / "categories.json"

# --- Настройки из .env ---
KEV_BASE_URL = os.getenv("KEV_BASE_URL", "http://127.0.0.1:8009")
KEV_MODEL = os.getenv("KEV_MODEL", "kev-latest")

DEFAULT_CATEGORIES = {
    "tech": "💻 Технологии",
    "news": "📰 Новости",
    "finance": "💰 Финансы",
    "spam": "🚫 Спам",
    "personal": "👤 Личное",
    "other": "📦 Другое",
}


def load_categories() -> dict:
    """Читает categories.json. Если файла нет — создаёт с дефолтными."""
    if not CATEGORIES_FILE.exists():
        CATEGORIES_FILE.write_text(
            json.dumps({"categories": DEFAULT_CATEGORIES}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return DEFAULT_CATEGORIES

    try:
        data = json.loads(CATEGORIES_FILE.read_text(encoding="utf-8"))
        cats = data.get("categories", {})
        if not isinstance(cats, dict) or not cats:
            return DEFAULT_CATEGORIES
        return cats
    except Exception:
        return DEFAULT_CATEGORIES


def get_categories() -> dict:
    """Возвращает актуальный словарь категорий."""
    return load_categories()


# Подключение к локальному Kev-серверу
_kev_client = TypeSafeClient(
    api_key="local",
    base_url=KEV_BASE_URL,
    model=KEV_MODEL,
)


def classify_message(text: str) -> dict:
    """
    Классифицирует текст сообщения через Kev.
    Возвращает словарь с результатами.
    При ошибке (Kev не запущен) возвращает безопасные дефолты.
    """
    if not text or not text.strip():
        return {
            "kev_important": None,
            "kev_category": None,
            "kev_urgency": None,
            "kev_error": "empty_text",
        }

    categories = load_categories()
    criteria = {key: None for key in categories.keys()}

    try:
        response = _kev_client.system_one(
            state=text,
            questions={
                "important": Noul(
                    instructions="Is this message important and worth reading?"
                ),
                "category": Choice(
                    instructions="What is the category of this message?",
                    criteria=criteria,
                ),
                "urgency": Score(
                    instructions="How urgent is this message?",
                    criteria=["ignore", "read later", "read now"],
                ),
            },
        )

        return {
            "kev_important": round(float(response.nouls["important"].noul), 4),
            "kev_category": response.choices["category"].choice,
            "kev_urgency": round(float(response.scores["urgency"].score), 4),
            "kev_error": None,
        }

    except Exception as e:
        return {
            "kev_important": None,
            "kev_category": None,
            "kev_urgency": None,
            "kev_error": str(e)[:200],
        }