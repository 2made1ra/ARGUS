from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ServiceAlias:
    category: str
    aliases: tuple[str, ...]


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

SERVICE_ALIASES: tuple[ServiceAlias, ...] = (
    ServiceAlias(
        "звук",
        ("звук", "звуку", "акустик", "микрофон", "радиомикрофон", "радики"),
    ),
    ServiceAlias(
        "свет",
        ("свет", "свету", "световое", "световым", "напольные приборы"),
    ),
    ServiceAlias(
        "сценические конструкции",
        ("сцен", "ферм", "граунд", "ground support"),
    ),
    ServiceAlias(
        "мультимедиа",
        ("экран", "экраны", "проектор", "мультимедиа", "led", "лед"),
    ),
    ServiceAlias(
        "кейтеринг",
        ("кейтеринг", "кейтерингу", "фуршет", "банкет", "welcome drink"),
    ),
    ServiceAlias(
        "welcome-зона",
        ("welcome-зон", "welcome зон", "велком", "велкам", "регистрац"),
    ),
    ServiceAlias(
        "персонал",
        ("ведущ", "хостес", "хостесс", "персонал", "координатор"),
    ),
    ServiceAlias("логистика", ("логистик", "доставка", "транспорт")),
    ServiceAlias("декор", ("декор", "оформлен", "бренд-волл", "фотозон", "навигац")),
    ServiceAlias(
        "мебель",
        ("мебел", "стойка регистрации", "ресепшен", "стол", "стуль"),
    ),
    ServiceAlias("площадка", ("площадк", "лофт")),
    ServiceAlias("оборудование", ("оборудован",)),
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
    lower = lower.lower()
    categories: list[str] = []
    for service_alias in SERVICE_ALIASES:
        if any(alias in lower for alias in service_alias.aliases):
            categories.append(service_alias.category)
    return _unique(categories)


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
