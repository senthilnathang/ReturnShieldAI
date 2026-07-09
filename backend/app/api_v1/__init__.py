from fastapi import APIRouter

from .health import router as health_router
from .imports import router as imports_router
from .returns import router as returns_router
from .fraud_cases import router as fraud_cases_router
from .dashboard import router as dashboard_router
from .customers import router as customers_router
from .orders import router as orders_router

router = APIRouter(prefix="/api/v1")
router.include_router(health_router)
router.include_router(imports_router)
router.include_router(returns_router)
router.include_router(fraud_cases_router)
router.include_router(dashboard_router)
router.include_router(customers_router)
router.include_router(orders_router)

__all__ = ["router"]
