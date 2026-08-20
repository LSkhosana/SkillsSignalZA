"""V1 router aggregator.

HTTP transport and request validation live here. Assessment scoring,
evidence extraction and persistence adapters must not be implemented
in this package.
"""

from fastapi import APIRouter

from app.api.v1 import assessments, documents, health, reports

router = APIRouter()
router.include_router(health.router, tags=["health"])
router.include_router(assessments.router, prefix="/assessments", tags=["assessments"])
router.include_router(documents.router, prefix="/documents", tags=["documents"])
router.include_router(reports.router, prefix="/reports", tags=["reports"])
