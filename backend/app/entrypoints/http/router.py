from fastapi import APIRouter

from app.entrypoints.http.assistant import router as assistant_router
from app.entrypoints.http.catalog import router as catalog_router
from app.entrypoints.http.contractors import router as contractors_router
from app.entrypoints.http.documents import router as documents_router
from app.entrypoints.http.search import router as search_router
from app.entrypoints.http.streams import router as streams_router

router = APIRouter()
router.include_router(assistant_router)
router.include_router(catalog_router)
router.include_router(documents_router)
router.include_router(contractors_router)
router.include_router(search_router)
router.include_router(streams_router)

__all__ = ["router"]
