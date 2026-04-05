from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, status

from app.api.dependencies import get_current_user, get_order_placement_service
from app.core.settings import get_settings
from app.data.mock_data_loader import clear_mock_data_cache
from app.models.user import User
from app.schemas.order_placement import (
    CartItemMutationRequest,
    CartItemQuantityUpdateRequest,
    CartResponse,
    CatalogListResponse,
    CheckoutValidateRequest,
    CheckoutValidateResponse,
    OrderCreateRequest,
    OrderCreateResponse,
    OrderLifecycleSimResponse,
    PaymentAuthorizeSimRequest,
    PaymentAuthorizeSimResponse,
)
from app.services.order_placement_service import OrderPlacementService

router = APIRouter()


@router.get("/catalog/items", response_model=CatalogListResponse)
def list_catalog_items(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=8, ge=1, le=50),
    search: str | None = Query(default=None),
    restaurant: str | None = Query(default=None),
    cuisine: str | None = Query(default=None),
    availability: str = Query(default="all", pattern="^(all|available|out_of_stock)$"),
    sort_by: str = Query(default="featured", pattern="^(featured|name|price_asc|price_desc|restaurant)$"),
    order_placement_service: OrderPlacementService = Depends(get_order_placement_service),
) -> CatalogListResponse:
    items, total_items, restaurants, cuisines = order_placement_service.list_catalog(
        page=page,
        page_size=page_size,
        search=search,
        restaurant=restaurant,
        cuisine=cuisine,
        availability=availability,
        sort_by=sort_by,
    )
    total_pages = max(1, (total_items + page_size - 1) // page_size)
    return CatalogListResponse(
        items=items,
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
        restaurants=restaurants,
        cuisines=cuisines,
    )


@router.get("/cart", response_model=CartResponse)
def get_cart(
    current_user: User = Depends(get_current_user),
    order_placement_service: OrderPlacementService = Depends(get_order_placement_service),
) -> CartResponse:
    return order_placement_service.get_cart(current_user)


@router.post("/cart/items", response_model=CartResponse, status_code=status.HTTP_201_CREATED)
def add_cart_item(
    payload: CartItemMutationRequest,
    current_user: User = Depends(get_current_user),
    order_placement_service: OrderPlacementService = Depends(get_order_placement_service),
) -> CartResponse:
    return order_placement_service.add_cart_item(current_user, payload)


@router.patch("/cart/items/{item_id}", response_model=CartResponse)
def update_cart_item(
    item_id: str,
    payload: CartItemQuantityUpdateRequest,
    current_user: User = Depends(get_current_user),
    order_placement_service: OrderPlacementService = Depends(get_order_placement_service),
) -> CartResponse:
    return order_placement_service.update_cart_item(current_user, item_id, payload.quantity)


@router.delete("/cart/items/{item_id}", response_model=CartResponse)
def remove_cart_item(
    item_id: str,
    current_user: User = Depends(get_current_user),
    order_placement_service: OrderPlacementService = Depends(get_order_placement_service),
) -> CartResponse:
    return order_placement_service.remove_cart_item(current_user, item_id)


@router.post("/checkout/validate", response_model=CheckoutValidateResponse)
def validate_checkout(
    payload: CheckoutValidateRequest,
    current_user: User = Depends(get_current_user),
    order_placement_service: OrderPlacementService = Depends(get_order_placement_service),
) -> CheckoutValidateResponse:
    return order_placement_service.validate_checkout(current_user, payload)


@router.post("/payments/authorize-sim", response_model=PaymentAuthorizeSimResponse)
def authorize_payment_sim(
    payload: PaymentAuthorizeSimRequest,
    _: User = Depends(get_current_user),
    order_placement_service: OrderPlacementService = Depends(get_order_placement_service),
) -> PaymentAuthorizeSimResponse:
    return order_placement_service.authorize_payment_sim(payload)


@router.post("/orders", response_model=OrderCreateResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreateRequest,
    current_user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    order_placement_service: OrderPlacementService = Depends(get_order_placement_service),
) -> OrderCreateResponse:
    return order_placement_service.create_order(
        user=current_user,
        payload=payload,
        idempotency_key=idempotency_key,
    )


@router.get("/orders/{order_id}/lifecycle-sim", response_model=OrderLifecycleSimResponse)
def get_order_lifecycle_sim(
    order_id: str,
    scenario_id: str = Query(default="default"),
    current_user: User = Depends(get_current_user),
    order_placement_service: OrderPlacementService = Depends(get_order_placement_service),
) -> OrderLifecycleSimResponse:
    return order_placement_service.get_order_lifecycle_sim(
        user=current_user,
        order_id=order_id,
        scenario_id=scenario_id,
    )


@router.post("/dev/mock-data/reload", status_code=status.HTTP_204_NO_CONTENT)
def reload_mock_data_cache() -> None:
    settings = get_settings()
    if not settings.is_dev:
        return None

    clear_mock_data_cache()
    return None
