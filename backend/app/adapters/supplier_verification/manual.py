from __future__ import annotations

from app.features.assistant.dto import SupplierVerificationResult


class ManualNotVerifiedSupplierVerificationAdapter:
    async def verify_by_inn_or_ogrn(
        self,
        *,
        inn: str | None,
        ogrn: str | None,
        supplier_name: str | None,
    ) -> SupplierVerificationResult:
        return SupplierVerificationResult(
            item_id=None,
            supplier_name=supplier_name,
            supplier_inn=inn,
            ogrn=ogrn,
            legal_name=None,
            status="not_verified",
            source="manual_not_verified",
            checked_at=None,
            risk_flags=["verification_adapter_not_configured"],
            message="Автоматическая проверка поставщиков не настроена",
        )


__all__ = ["ManualNotVerifiedSupplierVerificationAdapter"]
