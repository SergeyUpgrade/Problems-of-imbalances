from fastapi import APIRouter
from .endpoints import router as coverage_router

router = APIRouter()
router.include_router(coverage_router, prefix="/api", tags=["coverage"])
