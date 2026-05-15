from __future__ import annotations

import re
from typing import Literal

ServiceCategory = Literal[
    "звук",
    "свет",
    "сценические конструкции",
    "мультимедиа",
    "кейтеринг",
    "welcome-зона",
    "персонал",
    "логистика",
    "декор",
    "мебель",
    "площадка",
    "проживание",
    "полиграфия",
    "развлечения",
    "материалы",
    "техника",
    "спортивный инвентарь",
    "прочее",
]

SERVICE_CATEGORIES: tuple[ServiceCategory, ...] = (
    "звук",
    "свет",
    "сценические конструкции",
    "мультимедиа",
    "кейтеринг",
    "welcome-зона",
    "персонал",
    "логистика",
    "декор",
    "мебель",
    "площадка",
    "проживание",
    "полиграфия",
    "развлечения",
    "материалы",
    "техника",
    "спортивный инвентарь",
    "прочее",
)

GENERIC_CATEGORIES = frozenset(
    {
        "аренда",
        "аренда оборудования",
        "оборудование",
        "продажа",
        "работы",
        "товары",
        "услуга",
        "услуги",
    },
)

_ALIASES: dict[ServiceCategory, tuple[str, ...]] = {
    "звук": ("звук", "аудио", "акустик", "микрофон", "колонк", "сабвуфер"),
    "свет": ("свет", "светодиод", "прожектор", "led", "лайт"),
    "сценические конструкции": ("сцен", "ферм", "подиум", "конструкц", "трасс"),
    "мультимедиа": ("экран", "проектор", "мультимедиа", "видео", "плазм", "тв"),
    "кейтеринг": ("кейтер", "питани", "еда", "кофе", "фуршет", "банкет"),
    "welcome-зона": ("welcome", "велком", "регистрац", "ресепш", "аккредитац"),
    "персонал": ("персонал", "хостес", "монтажник", "техник", "оператор"),
    "логистика": ("логист", "доставк", "транспорт", "грузчик", "перевоз"),
    "декор": ("декор", "оформлен", "цвет", "флорист", "баннер"),
    "мебель": ("мебел", "стул", "стол", "диван", "кресл"),
    "площадка": ("площадк", "зал", "арена", "конференц", "помещен"),
    "проживание": ("проживан", "отель", "гостиниц", "номер", "ноч"),
    "полиграфия": ("полиграф", "печать", "листовк", "буклет", "бейдж"),
    "развлечения": ("развлеч", "аниматор", "ведущ", "артист", "шоу"),
    "материалы": ("материал", "мдф", "расходник", "кабель", "коммутац"),
    "техника": ("техник", "ноутбук", "компьютер", "оборудован"),
    "спортивный инвентарь": ("спорт", "инвентар", "мяч", "форма"),
    "прочее": ("прочее",),
}


def is_generic_category(value: str | None) -> bool:
    normalized = normalize_service_category_text(value)
    return normalized is None or normalized in GENERIC_CATEGORIES


def normalize_service_category_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", value.strip()).casefold()
    return normalized or None


def validate_service_category(value: str) -> ServiceCategory:
    normalized = normalize_service_category_text(value)
    if normalized not in SERVICE_CATEGORIES:
        raise ValueError(f"Unknown service category: {value}")
    return normalized  # type: ignore[return-value]


def infer_service_category(value: str | None) -> ServiceCategory | None:
    normalized = normalize_service_category_text(value)
    if normalized is None or normalized in GENERIC_CATEGORIES:
        return None
    if normalized in SERVICE_CATEGORIES:
        return normalized  # type: ignore[return-value]

    for category, aliases in _ALIASES.items():
        if any(alias in normalized for alias in aliases):
            return category
    return None


__all__ = [
    "GENERIC_CATEGORIES",
    "SERVICE_CATEGORIES",
    "ServiceCategory",
    "infer_service_category",
    "is_generic_category",
    "normalize_service_category_text",
    "validate_service_category",
]
