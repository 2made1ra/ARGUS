from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class AliasEntry:
    term: str
    match_type: Literal["exact", "phrase", "stem"] = "phrase"


@dataclass(frozen=True, slots=True)
class ServiceAlias:
    category: str
    aliases: tuple[AliasEntry, ...]


@dataclass(frozen=True, slots=True)
class ServiceNeedTemplate:
    category: str
    priority: str = "required"
    source: str = "explicit"
    reason: str | None = None
    notes: str | None = None


CORE_SERVICE_CATEGORIES: tuple[str, ...] = (
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
)


def _alias(
    term: str,
    match_type: Literal["exact", "phrase", "stem"] = "phrase",
) -> AliasEntry:
    return AliasEntry(term=term, match_type=match_type)


def _alias_matches(alias: AliasEntry, lower: str) -> bool:
    term = alias.term.lower()
    if alias.match_type == "stem":
        return (
            re.search(
                rf"(?<![0-9a-zа-я]){re.escape(term)}[0-9a-zа-я-]*",
                lower,
            )
            is not None
        )
    if alias.match_type == "exact":
        return (
            re.search(
                rf"(?<![0-9a-zа-я]){re.escape(term)}(?![0-9a-zа-я])",
                lower,
            )
            is not None
        )
    return term in lower


SERVICE_ALIASES: tuple[ServiceAlias, ...] = (
    ServiceAlias(
        "звук",
        (
            _alias("звук", "exact"),
            _alias("звуку", "exact"),
            _alias("акустик", "stem"),
            _alias("микрофон", "phrase"),
            _alias("радиомикрофон", "phrase"),
            _alias("радики", "exact"),
        ),
    ),
    ServiceAlias(
        "свет",
        (
            _alias("свет", "exact"),
            _alias("свету", "exact"),
            _alias("световое", "phrase"),
            _alias("световым", "phrase"),
            _alias("светодиод", "stem"),
            _alias("напольные приборы", "phrase"),
        ),
    ),
    ServiceAlias(
        "сценические конструкции",
        (
            _alias("сцен", "stem"),
            _alias("ферм", "stem"),
            _alias("граунд", "phrase"),
            _alias("ground support", "phrase"),
        ),
    ),
    ServiceAlias(
        "мультимедиа",
        (
            _alias("экран", "exact"),
            _alias("экраны", "exact"),
            _alias("проектор", "phrase"),
            _alias("мультимедиа", "phrase"),
            _alias("led", "exact"),
            _alias("лед", "exact"),
        ),
    ),
    ServiceAlias(
        "кейтеринг",
        (
            _alias("кейтеринг", "phrase"),
            _alias("кейтерингу", "phrase"),
            _alias("кофе брейк", "phrase"),
            _alias("кофе-брейк", "phrase"),
            _alias("фуршет", "phrase"),
            _alias("банкет", "phrase"),
            _alias("обед", "phrase"),
            _alias("welcome drink", "phrase"),
        ),
    ),
    ServiceAlias(
        "welcome-зона",
        (
            _alias("welcome-зон", "stem"),
            _alias("welcome зон", "phrase"),
            _alias("велком", "phrase"),
            _alias("велкам", "phrase"),
            _alias("регистрац", "stem"),
        ),
    ),
    ServiceAlias(
        "персонал",
        (
            _alias("ведущ", "stem"),
            _alias("хостес", "phrase"),
            _alias("хостесс", "phrase"),
            _alias("персонал", "phrase"),
            _alias("координатор", "phrase"),
        ),
    ),
    ServiceAlias(
        "логистика",
        (
            _alias("логистик", "stem"),
            _alias("доставка", "exact"),
            _alias("транспорт", "exact"),
        ),
    ),
    ServiceAlias(
        "декор",
        (
            _alias("декор", "phrase"),
            _alias("оформлен", "stem"),
            _alias("бренд-волл", "phrase"),
            _alias("фотозон", "stem"),
            _alias("навигац", "stem"),
        ),
    ),
    ServiceAlias(
        "мебель",
        (
            _alias("мебел", "stem"),
            _alias("стойка регистрации", "phrase"),
            _alias("ресепшен", "phrase"),
            _alias("стол", "exact"),
            _alias("стуль", "stem"),
        ),
    ),
    ServiceAlias("площадка", (_alias("площадк", "stem"), _alias("лофт", "phrase"))),
    ServiceAlias(
        "спортивный инвентарь",
        (
            _alias("спортивный инвентарь", "phrase"),
            _alias("спортивного инвентаря", "phrase"),
            _alias("спортинвентар", "stem"),
        ),
    ),
    ServiceAlias(
        "оборудование",
        (
            _alias("оборудован", "stem"),
            _alias("инвентар", "stem"),
            _alias("спортинвентар", "stem"),
        ),
    ),
)

SERVICE_BUNDLES: dict[str, tuple[ServiceNeedTemplate, ...]] = {
    "welcome-зона": (
        ServiceNeedTemplate(
            category="мебель",
            priority="nice_to_have",
            source="policy_inferred",
            reason="welcome-зона",
            notes="стойка регистрации или ресепшен",
        ),
        ServiceNeedTemplate(
            category="персонал",
            priority="nice_to_have",
            source="policy_inferred",
            reason="welcome-зона",
            notes="хостес или регистрационный персонал",
        ),
        ServiceNeedTemplate(
            category="декор",
            priority="nice_to_have",
            source="policy_inferred",
            reason="welcome-зона",
            notes="навигация, бренд-волл или фотозона",
        ),
        ServiceNeedTemplate(
            category="мультимедиа",
            priority="nice_to_have",
            source="policy_inferred",
            reason="welcome-зона",
            notes="экран или навигационный носитель",
        ),
        ServiceNeedTemplate(
            category="кейтеринг",
            priority="nice_to_have",
            source="policy_inferred",
            reason="welcome-зона",
            notes="опциональный welcome drink",
        ),
    )
}

VENUE_CONSTRAINT_IMPLICATIONS: dict[str, tuple[ServiceNeedTemplate, ...]] = {
    "площадка без подвеса": (
        ServiceNeedTemplate(
            category="сценические конструкции",
            priority="nice_to_have",
            source="policy_inferred",
            reason="площадка без подвеса",
            notes="искать ground support, фермы или самонесущие конструкции",
        ),
        ServiceNeedTemplate(
            category="свет",
            priority="nice_to_have",
            source="policy_inferred",
            reason="площадка без подвеса",
            notes="искать стойки, напольные приборы или свет без подвеса",
        ),
        ServiceNeedTemplate(
            category="мультимедиа",
            priority="nice_to_have",
            source="policy_inferred",
            reason="площадка без подвеса",
            notes="искать напольные или самонесущие экраны",
        ),
    )
}

CITY_ALIASES: dict[str, tuple[str, ...]] = {
    "Екатеринбург": ("екатеринбург", "екатеринбурге", "екате", "екб"),
    "Москва": ("москва", "москве"),
    "Санкт-Петербург": ("санкт-петербург", "петербург", "спб"),
}

EVENT_TYPE_ALIASES: dict[str, tuple[str, ...]] = {
    "корпоратив": ("корпоратив", "корпоративный"),
    "конференция": ("конференц",),
    "презентация продукта": ("презентац", "продукт"),
    "выпускной": ("выпускн",),
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
    "инвентар",
)

CONTEXTUAL_BRIEF_PHRASES: tuple[str, ...] = (
    "тогда",
    "под это",
    "в бриф",
    "добавь",
    "укажи",
)


def service_categories_for(lower: str) -> list[str]:
    lower = lower.lower()
    categories: list[str] = []
    for service_alias in SERVICE_ALIASES:
        if any(_alias_matches(alias, lower) for alias in service_alias.aliases):
            categories.append(service_alias.category)
    if _mentions_sports_inventory(lower):
        categories = [
            category
            for category in categories
            if category != "оборудование"
        ]
    return _unique(categories)


def _mentions_sports_inventory(lower: str) -> bool:
    return "спортинвентар" in lower or (
        "спортив" in lower and "инвентар" in lower
    )


def service_bundle_templates_for(category: str) -> tuple[ServiceNeedTemplate, ...]:
    return SERVICE_BUNDLES.get(category, ())


def venue_constraint_templates_for(
    constraints: list[str],
) -> list[ServiceNeedTemplate]:
    templates: list[ServiceNeedTemplate] = []
    for constraint in constraints:
        templates.extend(VENUE_CONSTRAINT_IMPLICATIONS.get(constraint, ()))
    return templates


def canonical_city_for(lower: str) -> str | None:
    lower = lower.lower()
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
    "CORE_SERVICE_CATEGORIES",
    "DIRECT_SEARCH_PHRASES",
    "SEARCH_NOUNS",
    "SERVICE_ALIASES",
    "SERVICE_BUNDLES",
    "ServiceNeedTemplate",
    "VENUE_CONSTRAINT_IMPLICATIONS",
    "canonical_city_for",
    "event_type_for",
    "service_categories_for",
    "service_bundle_templates_for",
    "venue_constraint_templates_for",
]
