from fastapi import APIRouter

from app.api.routes.account_orders import router as account_order_router
from app.api.routes.auth import router as auth_router
from app.api.routes.intent_faq import router as intent_faq_router
from app.api.routes.order_placement import router as order_placement_router
from app.api.routes.refunds import router as refunds_router

router = APIRouter()
router.include_router(auth_router, tags=["auth"])
router.include_router(account_order_router, tags=["account-orders"])
router.include_router(intent_faq_router, tags=["intent-faq"])
router.include_router(order_placement_router, tags=["order-placement"])
router.include_router(refunds_router, tags=["refunds"])
