from __future__ import annotations

from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


class _FakeEngine:
    def __init__(self) -> None:
        self.disposed = False
        self.database_url: str | None = None

    async def dispose(self) -> None:
        self.disposed = True


class _FakeSession:
    def __init__(self) -> None:
        self.closed = False
        self.committed = False
        self.rolled_back = False

    async def close(self) -> None:
        self.closed = True

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class _FakeSessionmaker:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session
        self.called = False

    def __call__(self) -> _FakeSession:
        self.called = True
        return self._session


class _FakeImportPricesCsvUseCase:
    calls: list[dict[str, object]] = []
    initializations: list[dict[str, object]] = []

    def __init__(self, **kwargs: object) -> None:
        self.dependencies = kwargs
        self.initializations.append(kwargs)

    async def execute(
        self,
        *,
        filename: str,
        content: bytes,
        source_path: str | None = None,
    ) -> SimpleNamespace:
        self.calls.append(
            {"filename": filename, "content": content, "source_path": source_path},
        )
        return SimpleNamespace(
            filename=filename,
            status="IMPORTED",
            valid_row_count=2,
            invalid_row_count=1,
            duplicate_file=False,
        )


@pytest.fixture
def seed_cli_module() -> ModuleType:
    from app.entrypoints.cli import seed_demo_catalog

    return seed_demo_catalog


def _patch_composition(
    monkeypatch: pytest.MonkeyPatch,
    seed_cli_module: ModuleType,
    *,
    csv_path: Path,
) -> tuple[_FakeEngine, _FakeSessionmaker]:
    engine = _FakeEngine()
    session = _FakeSession()
    sessionmaker = _FakeSessionmaker(session)

    _FakeImportPricesCsvUseCase.calls.clear()
    _FakeImportPricesCsvUseCase.initializations.clear()
    monkeypatch.setattr(
        seed_cli_module,
        "get_settings",
        lambda: SimpleNamespace(
            database_url="postgresql+asyncpg://demo:demo@localhost/demo",
            argus_demo_catalog_csv_path=csv_path,
            catalog_embedding_model="demo-catalog-embedding-model",
        ),
    )
    def _make_engine(database_url: str) -> _FakeEngine:
        engine.database_url = database_url
        return engine

    monkeypatch.setattr(seed_cli_module, "make_engine", _make_engine)
    monkeypatch.setattr(seed_cli_module, "make_sessionmaker", lambda _: sessionmaker)
    monkeypatch.setattr(
        seed_cli_module,
        "SqlAlchemyPriceImportRepository",
        lambda session: SimpleNamespace(kind="imports", session=session),
    )
    monkeypatch.setattr(
        seed_cli_module,
        "SqlAlchemyPriceItemRepository",
        lambda session: SimpleNamespace(kind="items", session=session),
    )
    monkeypatch.setattr(
        seed_cli_module,
        "ImportPricesCsvUseCase",
        _FakeImportPricesCsvUseCase,
    )
    return engine, sessionmaker


def test_default_path_comes_from_settings_and_calls_use_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    seed_cli_module: ModuleType,
) -> None:
    csv_path = tmp_path / "default-prices.csv"
    csv_path.write_bytes(b"name,unit_price\nsound,100\n")
    engine, sessionmaker = _patch_composition(
        monkeypatch,
        seed_cli_module,
        csv_path=csv_path,
    )

    exit_code = seed_cli_module.main([])

    assert exit_code == 0
    assert engine.database_url == "postgresql+asyncpg://demo:demo@localhost/demo"
    assert sessionmaker.called is True
    assert engine.disposed is True
    assert _FakeImportPricesCsvUseCase.initializations == [
        {
            "imports": SimpleNamespace(kind="imports", session=sessionmaker._session),
            "items": SimpleNamespace(kind="items", session=sessionmaker._session),
            "uow": _FakeImportPricesCsvUseCase.initializations[0]["uow"],
            "embedding_model": "demo-catalog-embedding-model",
        },
    ]
    assert _FakeImportPricesCsvUseCase.calls == [
        {
            "filename": "default-prices.csv",
            "content": b"name,unit_price\nsound,100\n",
            "source_path": str(csv_path),
        },
    ]
    output = capsys.readouterr().out
    assert "default-prices.csv" in output
    assert "status=IMPORTED" in output
    assert "valid=2" in output
    assert "invalid=1" in output
    assert "duplicate=no" in output


def test_csv_argument_overrides_settings_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    seed_cli_module: ModuleType,
) -> None:
    settings_csv = tmp_path / "settings-prices.csv"
    override_csv = tmp_path / "override-prices.csv"
    settings_csv.write_bytes(b"name,unit_price\nsettings,100\n")
    override_csv.write_bytes(b"name,unit_price\noverride,200\n")
    _patch_composition(monkeypatch, seed_cli_module, csv_path=settings_csv)

    exit_code = seed_cli_module.main(["--csv", str(override_csv)])

    assert exit_code == 0
    assert _FakeImportPricesCsvUseCase.calls == [
        {
            "filename": "override-prices.csv",
            "content": b"name,unit_price\noverride,200\n",
            "source_path": str(override_csv),
        },
    ]


def test_missing_csv_path_exits_non_zero_with_clear_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    seed_cli_module: ModuleType,
) -> None:
    missing_csv = tmp_path / "missing-prices.csv"
    _patch_composition(monkeypatch, seed_cli_module, csv_path=missing_csv)

    with pytest.raises(SystemExit) as exc_info:
        seed_cli_module.main([])

    assert exc_info.value.code == 1
    error = capsys.readouterr().err
    assert "CSV file not found" in error
    assert str(missing_csv) in error
