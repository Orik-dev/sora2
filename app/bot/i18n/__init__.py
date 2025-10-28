from __future__ import annotations
import json
from functools import lru_cache
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.users.service import get_locale as repo_get_locale  # см. файл ниже

@lru_cache(maxsize=1)
def _load_locales() -> dict[str, dict[str, str]]:
    with open("app/bot/i18n/en.json", "r", encoding="utf-8") as f:
        en = json.load(f)
    with open("app/bot/i18n/ru.json", "r", encoding="utf-8") as f:
        ru = json.load(f)
    return {"en": en, "ru": ru}

async def get_user_lang(session: AsyncSession, user_id: int) -> str:
    lang = await repo_get_locale(session, user_id)
    return lang if lang in ("ru", "en") else "ru"

async def t(session: AsyncSession, user_id: int, key: str, **kwargs: Any) -> str:
    lang = await get_user_lang(session, user_id)
    bundle = _load_locales().get(lang, _load_locales()["ru"])
    text = bundle.get(key, key)
    try:
        return text.format(**kwargs)
    except Exception:
        return text
