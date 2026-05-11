from __future__ import annotations

from app.features.catalog.entities.price_item import PriceItemList
from app.features.catalog.ports import PriceItemRepository


class ListPriceItemsUseCase:
    def __init__(self, *, items: PriceItemRepository) -> None:
        self._items = items

    async def execute(self, *, limit: int = 50, offset: int = 0) -> PriceItemList:
        return await self._items.list_active(limit=limit, offset=offset)


__all__ = ["ListPriceItemsUseCase", "PriceItemList"]

