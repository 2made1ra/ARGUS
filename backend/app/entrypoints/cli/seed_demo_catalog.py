from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

from app.adapters.sqlalchemy.price_imports import SqlAlchemyPriceImportRepository
from app.adapters.sqlalchemy.price_items import SqlAlchemyPriceItemRepository
from app.adapters.sqlalchemy.session import make_engine, make_sessionmaker
from app.adapters.sqlalchemy.unit_of_work import SessionUnitOfWork
from app.config import get_settings
from app.features.catalog.use_cases.import_prices_csv import ImportPricesCsvUseCase


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed demo catalog from prices CSV.")
    parser.add_argument(
        "--csv",
        dest="csv_path",
        type=Path,
        help="Path to prices CSV. Defaults to ARGUS_DEMO_CATALOG_CSV_PATH.",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    csv_path = (
        args.csv_path
        if args.csv_path is not None
        else settings.argus_demo_catalog_csv_path
    )
    csv_path = csv_path.expanduser()
    if not csv_path.exists():
        print(f"CSV file not found: {csv_path}", file=sys.stderr)
        raise SystemExit(1)

    return asyncio.run(
        _seed_catalog(
            csv_path=csv_path,
            database_url=settings.database_url,
            embedding_model=settings.catalog_embedding_model,
        ),
    )


async def _seed_catalog(
    *,
    csv_path: Path,
    database_url: str,
    embedding_model: str,
) -> int:
    content = csv_path.read_bytes()
    engine = make_engine(database_url)
    session = None
    try:
        sessionmaker = make_sessionmaker(engine)
        session = sessionmaker()
        use_case = ImportPricesCsvUseCase(
            imports=SqlAlchemyPriceImportRepository(session),
            items=SqlAlchemyPriceItemRepository(session),
            uow=SessionUnitOfWork(session),
            embedding_model=embedding_model,
        )
        summary = await use_case.execute(
            filename=csv_path.name,
            content=content,
            source_path=str(csv_path),
        )
        duplicate = "yes" if summary.duplicate_file else "no"
        print(
            "Demo catalog seed: "
            f"filename={summary.filename} "
            f"status={summary.status} "
            f"valid={summary.valid_row_count} "
            f"invalid={summary.invalid_row_count} "
            f"duplicate={duplicate}",
        )
        return 0
    finally:
        if session is not None:
            await session.close()
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
