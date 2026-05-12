from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ServiceAlias:
    category: str
    aliases: tuple[str, ...]


SERVICE_ALIASES: tuple[ServiceAlias, ...] = (
    ServiceAlias("свет", ("свет", "свету", "световое", "световым")),
    ServiceAlias("звук", ("звук", "звуку", "акустик", "микрофон", "радиомикрофон")),
    ServiceAlias("кейтеринг", ("кейтеринг", "кейтерингу", "фуршет", "банкет")),
    ServiceAlias("сценические конструкции", ("сцен", "ферм", "подвес")),
    ServiceAlias("мультимедиа", ("экран", "проектор", "мультимедиа")),
    ServiceAlias("площадка", ("площадк", "лофт")),
    ServiceAlias("персонал", ("ведущ", "хостес", "персонал", "координатор")),
    ServiceAlias("оборудование", ("оборудован",)),
)

CITY_ALIASES: dict[str, tuple[str, ...]] = {
    "Екатеринбург": ("екатеринбург", "екатеринбурге", "екате", "екб"),
    "Москва": ("москва", "москве"),
    "Санкт-Петербург": ("санкт-петербург", "петербург", "спб"),
}

EVENT_TYPE_ALIASES: dict[str, tuple[str, ...]] = {
    "корпоратив": ("корпоратив", "корпоративный"),
    "конференция": ("конференц",),
    "презентация продукта": ("презентац", "продукт"),
    "мероприятие": ("мероприят",),
}

BRIEF_CREATION_PHRASES: tuple[str, ...] = (
    "нужно организовать",
    "надо организовать",
    "организовать",
    "организуем",
    "планируем",
    "планирую",
    "готовим",
    "собери бриф",
    "собрать бриф",
    "сформируй бриф",
    "нужно провести",
    "хочу",
)

DIRECT_SEARCH_PHRASES: tuple[str, ...] = (
    "найди",
    "подбери",
    "покажи",
    "посмотри",
    "есть кто",
    "есть что",
    "есть ",
)

SEARCH_NOUNS: tuple[str, ...] = (
    "подрядчик",
    "подрядчика",
    "поставщик",
    "поставщика",
    "исполнитель",
    "позици",
    "цена",
    "стоимость",
    "оборудован",
)

CONTEXTUAL_BRIEF_PHRASES: tuple[str, ...] = (
    "тогда",
    "под это",
    "в бриф",
    "добавь",
    "укажи",
)


def service_categories_for(lower: str) -> list[str]:
    categories: list[str] = []
    for service_alias in SERVICE_ALIASES:
        if any(alias in lower for alias in service_alias.aliases):
            categories.append(service_alias.category)
    return _unique(categories)


def canonical_city_for(lower: str) -> str | None:
    for city, aliases in CITY_ALIASES.items():
        if any(alias in lower for alias in aliases):
            return city
    return None


def event_type_for(lower: str) -> str | None:
    if "музыкаль" in lower and "вечер" in lower:
        return "музыкальный вечер"
    for event_type, aliases in EVENT_TYPE_ALIASES.items():
        if any(alias in lower for alias in aliases):
            return event_type
    return None


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result


__all__ = [
    "BRIEF_CREATION_PHRASES",
    "CONTEXTUAL_BRIEF_PHRASES",
    "DIRECT_SEARCH_PHRASES",
    "SEARCH_NOUNS",
    "SERVICE_ALIASES",
    "canonical_city_for",
    "event_type_for",
    "service_categories_for",
]
