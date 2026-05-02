from urllib.parse import urlsplit, urlunsplit

from celery import Celery  # type: ignore[import-untyped]

from app.config import get_settings


def _redis_url_with_db(redis_url: str, db_index: int) -> str:
    parts = urlsplit(redis_url)
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            f"/{db_index}",
            parts.query,
            parts.fragment,
        )
    )


def _redis_db_index(redis_url: str) -> int | None:
    path = urlsplit(redis_url).path.strip("/")
    if not path:
        return None
    return int(path)


settings = get_settings()
redis_db_index = _redis_db_index(settings.redis_url)

broker_url = (
    settings.redis_url
    if redis_db_index is not None
    else _redis_url_with_db(settings.redis_url, 0)
)
backend_url = _redis_url_with_db(
    settings.redis_url,
    (redis_db_index + 1) if redis_db_index is not None else 1,
)

celery_app = Celery("argus", broker=broker_url, backend=backend_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
celery_app.autodiscover_tasks(["app.entrypoints.celery.tasks"], related_name="ingest")

__all__ = ["celery_app"]
