from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest
from app.features.assistant.domain.tool_executor import ToolExecutor
from app.features.assistant.dto import (
    ActionPlan,
    AssistantInterfaceMode,
    BriefState,
    CatalogItemDetail,
    EventBriefWorkflowState,
    SupplierVerificationResult,
    VisibleCandidate,
)


class FakeCatalogItemDetailsTool:
    def __init__(self, details: dict[UUID, CatalogItemDetail]) -> None:
        self.details = details
        self.calls: list[UUID] = []

    async def get_item_details(self, *, item_id: UUID) -> CatalogItemDetail | None:
        self.calls.append(item_id)
        return self.details.get(item_id)


class FakeSupplierVerificationPort:
    def __init__(self, *, status: str = "active") -> None:
        self.status = status
        self.calls: list[dict[str, str | None]] = []

    async def verify_by_inn_or_ogrn(
        self,
        *,
        inn: str | None,
        ogrn: str | None,
        supplier_name: str | None,
    ) -> SupplierVerificationResult:
        self.calls.append(
            {"inn": inn, "ogrn": ogrn, "supplier_name": supplier_name},
        )
        return SupplierVerificationResult(
            item_id=None,
            supplier_name=supplier_name,
            supplier_inn=inn,
            ogrn=ogrn,
            legal_name=supplier_name,
            status=self.status,
            source="fake_registry",
            checked_at=None,
            risk_flags=[],
            message=None,
        )


def _detail(
    item_id: UUID,
    *,
    supplier: str = "ООО НИКА",
    supplier_inn: str | None = "7701234567",
) -> CatalogItemDetail:
    return CatalogItemDetail(
        id=item_id,
        name="Аренда света",
        category="Свет",
        unit="день",
        unit_price=Decimal("15000.00"),
        supplier=supplier,
        supplier_inn=supplier_inn,
        supplier_city="Екатеринбург",
        supplier_phone=None,
        supplier_email=None,
        supplier_status=None,
        source_text="Световой комплект",
    )


def _verification_plan() -> ActionPlan:
    return ActionPlan(
        interface_mode=AssistantInterfaceMode.BRIEF_WORKSPACE,
        workflow_stage=EventBriefWorkflowState.SUPPLIER_VERIFICATION,
        tool_intents=["verify_supplier_status"],
    )


@pytest.mark.asyncio
async def test_verification_requires_explicit_candidate_context() -> None:
    details = FakeCatalogItemDetailsTool(details={})
    verifier = FakeSupplierVerificationPort()
    executor = ToolExecutor(
        catalog_search=None,
        item_details=details,
        supplier_verification=verifier,
    )

    results = await executor.execute(
        action_plan=_verification_plan(),
        brief=BriefState(),
        brief_update=BriefState(),
        message="проверь найденных подрядчиков",
    )

    assert results.verification_results == []
    assert details.calls == []
    assert verifier.calls == []
    assert "verification_targets_missing" in results.skipped_actions


@pytest.mark.asyncio
async def test_verification_uses_candidate_item_ids_and_dedupes_by_inn() -> None:
    first_id = UUID("11111111-1111-1111-1111-111111111111")
    second_id = UUID("22222222-2222-2222-2222-222222222222")
    missing_inn_id = UUID("33333333-3333-3333-3333-333333333333")
    details = FakeCatalogItemDetailsTool(
        details={
            first_id: _detail(first_id, supplier="ООО НИКА"),
            second_id: _detail(second_id, supplier="ООО НИКА"),
            missing_inn_id: _detail(
                missing_inn_id,
                supplier="ИП Без ИНН",
                supplier_inn=None,
            ),
        },
    )
    verifier = FakeSupplierVerificationPort(status="active")
    executor = ToolExecutor(
        catalog_search=None,
        item_details=details,
        supplier_verification=verifier,
    )

    results = await executor.execute(
        action_plan=_verification_plan(),
        brief=BriefState(),
        brief_update=BriefState(),
        candidate_item_ids=[first_id, second_id, missing_inn_id],
    )

    assert details.calls == [first_id, second_id, missing_inn_id]
    assert verifier.calls == [
        {"inn": "7701234567", "ogrn": None, "supplier_name": "ООО НИКА"},
    ]
    assert [result.item_id for result in results.verification_results] == [
        first_id,
        second_id,
        missing_inn_id,
    ]
    assert [result.status for result in results.verification_results] == [
        "active",
        "active",
        "not_verified",
    ]
    missing_result = results.verification_results[-1]
    assert missing_result.risk_flags == ["supplier_inn_missing"]
    assert missing_result.source == "catalog"


@pytest.mark.asyncio
async def test_missing_verification_adapter_returns_not_verified_result() -> None:
    item_id = UUID("44444444-4444-4444-4444-444444444444")
    executor = ToolExecutor(
        catalog_search=None,
        item_details=FakeCatalogItemDetailsTool(details={item_id: _detail(item_id)}),
        supplier_verification=None,
    )

    results = await executor.execute(
        action_plan=_verification_plan(),
        brief=BriefState(),
        brief_update=BriefState(),
        candidate_item_ids=[item_id],
    )

    assert len(results.verification_results) == 1
    result = results.verification_results[0]
    assert result.item_id == item_id
    assert result.status == "not_verified"
    assert result.source == "manual_not_verified"
    assert result.risk_flags == ["verification_adapter_not_configured"]


@pytest.mark.asyncio
async def test_verification_targets_use_allowed_explicit_contexts() -> None:
    selected_id = UUID("55555555-5555-5555-5555-555555555555")
    visible_id = UUID("66666666-6666-6666-6666-666666666666")
    explicit_id = UUID("77777777-7777-7777-7777-777777777777")
    details = FakeCatalogItemDetailsTool(
        details={
            selected_id: _detail(selected_id, supplier="ООО Первый", supplier_inn="1"),
            visible_id: _detail(visible_id, supplier="ООО Второй", supplier_inn="2"),
            explicit_id: _detail(explicit_id, supplier="ООО Третий", supplier_inn="3"),
        },
    )
    verifier = FakeSupplierVerificationPort()
    executor = ToolExecutor(
        catalog_search=None,
        item_details=details,
        supplier_verification=verifier,
    )
    plan = ActionPlan(
        interface_mode=AssistantInterfaceMode.BRIEF_WORKSPACE,
        workflow_stage=EventBriefWorkflowState.SUPPLIER_VERIFICATION,
        tool_intents=["verify_supplier_status"],
        verification_targets=[explicit_id],
    )

    results = await executor.execute(
        action_plan=plan,
        brief=BriefState(selected_item_ids=[selected_id]),
        brief_update=BriefState(),
        visible_candidates=[
            VisibleCandidate(ordinal=1, item_id=visible_id, service_category="свет"),
        ],
    )

    assert details.calls == [selected_id, visible_id, explicit_id]
    assert [result.item_id for result in results.verification_results] == [
        selected_id,
        visible_id,
        explicit_id,
    ]


@pytest.mark.asyncio
async def test_verification_limits_candidate_targets_per_turn() -> None:
    item_ids = [
        UUID("88888888-8888-8888-8888-888888888881"),
        UUID("88888888-8888-8888-8888-888888888882"),
        UUID("88888888-8888-8888-8888-888888888883"),
        UUID("88888888-8888-8888-8888-888888888884"),
    ]
    details = FakeCatalogItemDetailsTool(
        details={
            item_id: _detail(
                item_id,
                supplier=f"ООО {index}",
                supplier_inn=f"770123456{index}",
            )
            for index, item_id in enumerate(item_ids, start=1)
        },
    )
    verifier = FakeSupplierVerificationPort()
    executor = ToolExecutor(
        catalog_search=None,
        item_details=details,
        supplier_verification=verifier,
        max_tool_calls_per_turn=3,
    )

    results = await executor.execute(
        action_plan=_verification_plan(),
        brief=BriefState(),
        brief_update=BriefState(),
        candidate_item_ids=item_ids,
    )

    assert details.calls == item_ids[:3]
    assert len(verifier.calls) == 3
    assert [result.item_id for result in results.verification_results] == item_ids[:3]
    assert f"verification_targets_skipped:{item_ids[3]}" in results.skipped_actions
