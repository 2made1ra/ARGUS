from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence

from app.adapters.llm.catalog_category_classifier import (
    LMStudioCatalogCategoryClassifier,
)
from app.adapters.sqlalchemy.price_items import SqlAlchemyPriceItemRepository
from app.adapters.sqlalchemy.session import make_engine, make_sessionmaker
from app.adapters.sqlalchemy.unit_of_work import SessionUnitOfWork
from app.config import get_settings
from app.features.catalog.use_cases.enrich_price_item_categories import (
    EnrichPriceItemCategoriesUseCase,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill canonical service categories for catalog items.",
    )
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args(argv)

    settings = get_settings()
    return asyncio.run(
        _enrich_categories(
            database_url=settings.database_url,
            base_url=settings.lm_studio_url,
            model=settings.lm_studio_llm_model,
            limit=args.limit,
        ),
    )


async def _enrich_categories(
    *,
    database_url: str,
    base_url: str,
    model: str,
    limit: int,
) -> int:
    engine = make_engine(database_url)
    session = None
    try:
        sessionmaker = make_sessionmaker(engine)
        session = sessionmaker()
        repository = SqlAlchemyPriceItemRepository(session)
        use_case = EnrichPriceItemCategoriesUseCase(
            items=repository,
            classifier=LMStudioCatalogCategoryClassifier(
                base_url=base_url,
                model=model,
            ),
            uow=SessionUnitOfWork(session),
            model=model,
        )
        result = await use_case.execute(limit=limit)
        print(
            "Catalog category enrichment: "
            f"total={result.total} "
            f"enriched={result.enriched} "
            f"failed={result.failed}",
        )
        return 0
    finally:
        if session is not None:
            await session.close()
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
