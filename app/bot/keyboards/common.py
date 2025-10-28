from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def kb_language() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
        InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en"),
    ]])

def kb_generate_type(strings: dict[str, str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=strings.get("gen.from_text",  "📝 Сгенерировать видео по тексту"),
                              callback_data="menu:text")],
         [InlineKeyboardButton(text=strings.get("gen.from_image", "📸 Сгенерировать видео по фото"),
                              callback_data="menu:image")],
    ])

def kb_vertical_toggle(*, is_vertical: bool) -> InlineKeyboardMarkup:
    label = "Вертикальное видео ✅" if is_vertical else "Вертикальное видео"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data="toggle:ar")]
    ])

def kb_main(strings: dict[str, str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=strings.get("menu.generate", "🎬 Создать видео"),
            callback_data="start:create_video"
        )]
    ])
