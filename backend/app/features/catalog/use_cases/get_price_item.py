from __future__ import annotations

from uuid import UUID

from app.features.catalog.entities.price_item import PriceItem, PriceItemSourceRef
from app.features.catalog.ports import PriceItemRepository


class GetPriceItemUseCase:
    def __init__(self, *, items: PriceItemRepository) -> None:
        self._items = items

    async def execute(
        self,
        item_id: UUID,
    ) -> tuple[PriceItem, list[PriceItemSourceRef]]:
        detail = await self._items.get_with_sources(item_id)
        return detail.item, detail.sources


__all__ = ["GetPriceItemUseCase"]
