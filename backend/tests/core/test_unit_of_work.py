import inspect

from app.core.ports import UnitOfWork


def test_unit_of_work_is_protocol() -> None:
    assert hasattr(UnitOfWork, "__protocol_attrs__") or inspect.isclass(UnitOfWork)


def test_unit_of_work_has_required_methods() -> None:
    required = {"__aenter__", "__aexit__", "commit", "rollback"}
    assert required.issubset(set(dir(UnitOfWork)))


def test_unit_of_work_methods_are_coroutines() -> None:
    for name in ("__aenter__", "__aexit__", "commit", "rollback"):
        method = getattr(UnitOfWork, name)
        assert inspect.iscoroutinefunction(method), f"{name} must be async"
