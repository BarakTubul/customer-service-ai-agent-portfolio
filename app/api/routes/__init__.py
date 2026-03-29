from fastapi import APIRouter

from app.api.routes.account_orders import router as account_order_router
from app.api.routes.auth import router as auth_router

router = APIRouter()
router.include_router(auth_router, tags=["auth"])
router.include_router(account_order_router, tags=["account-orders"])
