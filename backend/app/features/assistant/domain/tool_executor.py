from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from uuid import UUID

from app.features.assistant.brief import merge_brief
from app.features.assistant.domain.brief_renderer import BriefRenderer
from app.features.assistant.dto import (
    ActionPlan,
    BriefState,
    CatalogItemDetail,
    ChatTurn,
    FoundCatalogItem,
    SupplierVerificationResult,
    ToolResults,
    VisibleCandidate,
)
from app.features.assistant.ports import (
    BriefRendererTool,
    CatalogItemDetailsTool,
    CatalogSearchTool,
    SupplierVerificationPort,
)

_DEFAULT_MAX_TOOL_CALLS_PER_TURN = 3


class ToolExecutor:
    def __init__(
        self,
        *,
        catalog_search: CatalogSearchTool | None,
        item_details: CatalogItemDetailsTool | None,
        supplier_verification: SupplierVerificationPort | None = None,
        brief_renderer: BriefRendererTool | None = None,
        max_tool_calls_per_turn: int = _DEFAULT_MAX_TOOL_CALLS_PER_TURN,
    ) -> None:
        self._catalog_search = catalog_search
        self._item_details = item_details
        self._supplier_verification = supplier_verification
        self._brief_renderer = (
            brief_renderer if brief_renderer is not None else BriefRenderer()
        )
        self._max_tool_calls_per_turn = max(0, max_tool_calls_per_turn)

    async def execute(
        self,
        *,
        action_plan: ActionPlan,
        brief: BriefState,
        brief_update: BriefState,
        message: str = "",
        recent_turns: list[ChatTurn] | None = None,
        visible_candidates: list[VisibleCandidate] | None = None,
        candidate_item_ids: list[UUID] | None = None,
    ) -> ToolResults:
        del message, recent_turns
        calls = _CallBudget(self._max_tool_calls_per_turn)
        working_brief = brief
        found_items: list[FoundCatalogItem] = []
        item_details: list[CatalogItemDetail] = []
        verification_results: list[SupplierVerificationResult] = []
        skipped_actions: list[str] = []
        rendered_brief = None

        for intent in action_plan.tool_intents:
            if intent == "update_brief":
                working_brief = merge_brief(working_brief, brief_update)
                continue

            if intent == "search_items":
                search_results = await self._execute_searches(
                    action_plan=action_plan,
                    calls=calls,
                    skipped_actions=skipped_actions,
                )
                found_items.extend(search_results)
                continue

            if intent == "get_item_details":
                details = await self._execute_item_details(
                    item_ids=action_plan.item_detail_ids,
                    calls=calls,
                    skipped_actions=skipped_actions,
                )
                item_details.extend(details)
                continue

            if intent == "verify_supplier_status":
                if not calls.consume("verify_supplier_status", skipped_actions):
                    continue
                resolved = await self._execute_verification(
                    action_plan=action_plan,
                    brief=working_brief,
                    visible_candidates=visible_candidates or [],
                    candidate_item_ids=candidate_item_ids or [],
                    skipped_actions=skipped_actions,
                )
                verification_results.extend(resolved)
                continue

            if intent == "render_event_brief":
                if not calls.consume("render_event_brief", skipped_actions):
                    continue
                rendered_brief = self._brief_renderer.render(
                    brief=working_brief,
                    selected_items=[
                        detail
                        for detail in item_details
                        if detail.id in set(working_brief.selected_item_ids)
                    ],
                    verification_results=verification_results,
                )
                continue

            skipped_actions.append(f"unsupported_tool:{intent}")

        return ToolResults(
            brief=working_brief,
            found_items=found_items,
            item_details=item_details,
            verification_results=verification_results,
            rendered_brief=rendered_brief,
            skipped_actions=[*action_plan.skipped_actions, *skipped_actions],
        )

    async def _execute_searches(
        self,
        *,
        action_plan: ActionPlan,
        calls: _CallBudget,
        skipped_actions: list[str],
    ) -> list[FoundCatalogItem]:
        if self._catalog_search is None:
            skipped_actions.append("search_items_unavailable")
            return []

        found_items_by_id: dict[UUID, FoundCatalogItem] = {}
        ordered_item_ids: list[UUID] = []
        for request in action_plan.search_requests:
            if not calls.consume("search_items", skipped_actions):
                break
            results = await self._catalog_search.search_items(
                query=request.query,
                limit=request.limit,
                filters=request.filters,
            )
            for item in results:
                if item.id not in found_items_by_id:
                    found_items_by_id[item.id] = _tag_found_item(
                        item,
                        result_group=request.service_category,
                    )
                    ordered_item_ids.append(item.id)
                    continue
                found_items_by_id[item.id] = _append_matched_group(
                    found_items_by_id[item.id],
                    result_group=request.service_category,
                )
        return [found_items_by_id[item_id] for item_id in ordered_item_ids]

    async def _execute_item_details(
        self,
        *,
        item_ids: Iterable[UUID],
        calls: _CallBudget,
        skipped_actions: list[str],
    ) -> list[CatalogItemDetail]:
        if self._item_details is None:
            skipped_actions.append("item_details_unavailable")
            return []

        details: list[CatalogItemDetail] = []
        for item_id in _dedupe_uuid(item_ids):
            if not calls.consume("get_item_details", skipped_actions):
                break
            detail = await self._item_details.get_item_details(item_id=item_id)
            if detail is None:
                skipped_actions.append(f"item_detail_not_found:{item_id}")
                continue
            details.append(detail)
        return details

    async def _execute_verification(
        self,
        *,
        action_plan: ActionPlan,
        brief: BriefState,
        visible_candidates: list[VisibleCandidate],
        candidate_item_ids: list[UUID],
        skipped_actions: list[str],
    ) -> list[SupplierVerificationResult]:
        if self._item_details is None:
            skipped_actions.append("item_details_unavailable")
            return []

        target_ids = _verification_target_ids(
            action_plan=action_plan,
            brief=brief,
            visible_candidates=visible_candidates,
            candidate_item_ids=candidate_item_ids,
        )
        if not target_ids:
            skipped_actions.append("verification_targets_missing")
            return []
        target_ids = _limit_verification_targets(
            target_ids=target_ids,
            limit=self._max_tool_calls_per_turn,
            skipped_actions=skipped_actions,
        )

        details: list[CatalogItemDetail] = []
        for item_id in target_ids:
            detail = await self._item_details.get_item_details(item_id=item_id)
            if detail is None:
                skipped_actions.append(f"verification_item_not_found:{item_id}")
                continue
            details.append(detail)

        return await self._verification_results_for_details(details)

    async def _verification_results_for_details(
        self,
        details: list[CatalogItemDetail],
    ) -> list[SupplierVerificationResult]:
        results_by_item_id: dict[UUID, SupplierVerificationResult] = {}
        details_by_inn: dict[str, list[CatalogItemDetail]] = {}

        for detail in details:
            supplier_inn = _normalized_inn(detail.supplier_inn)
            if supplier_inn is None:
                results_by_item_id[detail.id] = _missing_inn_result(detail)
                continue
            details_by_inn.setdefault(supplier_inn, []).append(detail)

        for supplier_inn, grouped_details in details_by_inn.items():
            template = await self._verify_once(
                inn=supplier_inn,
                supplier_name=grouped_details[0].supplier,
            )
            for detail in grouped_details:
                results_by_item_id[detail.id] = _result_for_item(
                    detail=detail,
                    template=template,
                )

        return [
            results_by_item_id[detail.id]
            for detail in details
            if detail.id in results_by_item_id
        ]

    async def _verify_once(
        self,
        *,
        inn: str,
        supplier_name: str | None,
    ) -> SupplierVerificationResult:
        if self._supplier_verification is None:
            return _adapter_not_configured_result(
                inn=inn,
                supplier_name=supplier_name,
            )
        return await self._supplier_verification.verify_by_inn_or_ogrn(
            inn=inn,
            ogrn=None,
            supplier_name=supplier_name,
        )


class _CallBudget:
    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._used = 0

    def consume(self, intent: str, skipped_actions: list[str]) -> bool:
        if self._used >= self._limit:
            skipped_actions.append(f"tool_call_limit_reached:{intent}")
            return False
        self._used += 1
        return True


def _verification_target_ids(
    *,
    action_plan: ActionPlan,
    brief: BriefState,
    visible_candidates: list[VisibleCandidate],
    candidate_item_ids: list[UUID],
) -> list[UUID]:
    return _dedupe_uuid(
        [
            *brief.selected_item_ids,
            *candidate_item_ids,
            *[candidate.item_id for candidate in visible_candidates],
            *action_plan.verification_targets,
        ],
    )


def _dedupe_uuid(item_ids: Iterable[UUID]) -> list[UUID]:
    result: list[UUID] = []
    seen: set[UUID] = set()
    for item_id in item_ids:
        if item_id in seen:
            continue
        result.append(item_id)
        seen.add(item_id)
    return result


def _tag_found_item(
    item: FoundCatalogItem,
    *,
    result_group: str | None,
) -> FoundCatalogItem:
    categories = list(item.matched_service_categories)
    if result_group is not None and result_group not in categories:
        categories.append(result_group)
    return replace(
        item,
        result_group=item.result_group or result_group,
        matched_service_category=item.matched_service_category or result_group,
        matched_service_categories=categories,
    )


def _append_matched_group(
    item: FoundCatalogItem,
    *,
    result_group: str | None,
) -> FoundCatalogItem:
    if result_group is None or result_group in item.matched_service_categories:
        return item
    return replace(
        item,
        matched_service_categories=[
            *item.matched_service_categories,
            result_group,
        ],
    )


def _limit_verification_targets(
    *,
    target_ids: list[UUID],
    limit: int,
    skipped_actions: list[str],
) -> list[UUID]:
    if len(target_ids) <= limit:
        return target_ids
    for item_id in target_ids[limit:]:
        skipped_actions.append(f"verification_targets_skipped:{item_id}")
    return target_ids[:limit]


def _normalized_inn(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = "".join(char for char in value if char.isdigit())
    return normalized or None


def _missing_inn_result(detail: CatalogItemDetail) -> SupplierVerificationResult:
    return SupplierVerificationResult(
        item_id=detail.id,
        supplier_name=detail.supplier,
        supplier_inn=None,
        ogrn=None,
        legal_name=None,
        status="not_verified",
        source="catalog",
        checked_at=None,
        risk_flags=["supplier_inn_missing"],
        message="В строке каталога нет ИНН поставщика",
    )


def _adapter_not_configured_result(
    *,
    inn: str,
    supplier_name: str | None,
) -> SupplierVerificationResult:
    return SupplierVerificationResult(
        item_id=None,
        supplier_name=supplier_name,
        supplier_inn=inn,
        ogrn=None,
        legal_name=None,
        status="not_verified",
        source="manual_not_verified",
        checked_at=None,
        risk_flags=["verification_adapter_not_configured"],
        message="Автоматическая проверка поставщиков не настроена",
    )


def _result_for_item(
    *,
    detail: CatalogItemDetail,
    template: SupplierVerificationResult,
) -> SupplierVerificationResult:
    return SupplierVerificationResult(
        item_id=detail.id,
        supplier_name=template.supplier_name or detail.supplier,
        supplier_inn=template.supplier_inn or detail.supplier_inn,
        ogrn=template.ogrn,
        legal_name=template.legal_name,
        status=template.status,
        source=template.source,
        checked_at=template.checked_at,
        risk_flags=list(template.risk_flags),
        message=template.message,
    )


__all__ = ["ToolExecutor"]
