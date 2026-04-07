from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime, timedelta

from app.core.errors import ForbiddenError, NotFoundError, ValidationAppError
from app.core.settings import get_settings
from app.data.mock_data_loader import load_mock_data
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.schemas.order_placement import (
    CartItemMutationRequest,
    CartResponse,
    CatalogItemResponse,
    CheckoutValidateRequest,
    CheckoutValidateResponse,
    OrderCreateRequest,
    OrderCreateResponse,
    OrderLifecycleEventResponse,
    OrderLifecycleSimResponse,
    PaymentAuthorizeSimRequest,
    PaymentAuthorizeSimResponse,
)

_CARTS: dict[int, dict[str, int]] = {}
_IDEMPOTENT_ORDERS: dict[tuple[int, str], OrderCreateResponse] = {}


class OrderPlacementService:
    def __init__(self, order_repository: OrderRepository) -> None:
        self.order_repository = order_repository
        self.settings = get_settings()

    def list_catalog(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        restaurant: str | None,
        cuisine: str | None,
        availability: str,
        sort_by: str,
    ) -> tuple[list[CatalogItemResponse], int, list[str], list[str]]:
        catalog = list(self._load_catalog().values())

        restaurants = sorted({item.restaurant_name for item in catalog})
        cuisines = sorted({item.restaurant_cuisine for item in catalog if item.restaurant_cuisine})

        if search:
            query = search.strip().lower()
            catalog = [
                item
                for item in catalog
                if query in item.name.lower()
                or query in item.description.lower()
                or query in item.restaurant_name.lower()
            ]

        if restaurant:
            catalog = [item for item in catalog if item.restaurant_name == restaurant]

        if cuisine:
            catalog = [item for item in catalog if item.restaurant_cuisine == cuisine]

        if availability == "available":
            catalog = [item for item in catalog if item.in_stock]
        elif availability == "out_of_stock":
            catalog = [item for item in catalog if not item.in_stock]

        if sort_by == "name":
            catalog.sort(key=lambda item: item.name.lower())
        elif sort_by == "price_asc":
            catalog.sort(key=lambda item: item.price_cents)
        elif sort_by == "price_desc":
            catalog.sort(key=lambda item: item.price_cents, reverse=True)
        elif sort_by == "restaurant":
            catalog.sort(key=lambda item: (item.restaurant_name.lower(), item.name.lower()))
        else:
            catalog.sort(key=lambda item: item.name.lower())

        total_items = len(catalog)
        start = (page - 1) * page_size
        end = start + page_size
        return catalog[start:end], total_items, restaurants, cuisines

    def get_cart(self, user: User) -> CartResponse:
        return self._build_cart_response(user.id)

    def add_cart_item(self, user: User, payload: CartItemMutationRequest) -> CartResponse:
        item = self._load_catalog().get(payload.item_id)
        if item is None:
            raise NotFoundError("Catalog item not found")
        if not item.in_stock:
            raise ValidationAppError("Item is currently out of stock")

        cart = _CARTS.setdefault(user.id, {})
        current_qty = cart.get(payload.item_id, 0)
        new_qty = min(current_qty + payload.quantity, 20)
        cart[payload.item_id] = new_qty
        return self._build_cart_response(user.id)

    def update_cart_item(self, user: User, item_id: str, quantity: int) -> CartResponse:
        if item_id not in self._load_catalog():
            raise NotFoundError("Catalog item not found")

        cart = _CARTS.setdefault(user.id, {})
        if quantity <= 0:
            cart.pop(item_id, None)
        else:
            cart[item_id] = quantity
        return self._build_cart_response(user.id)

    def remove_cart_item(self, user: User, item_id: str) -> CartResponse:
        cart = _CARTS.setdefault(user.id, {})
        cart.pop(item_id, None)
        return self._build_cart_response(user.id)

    def validate_checkout(self, user: User, payload: CheckoutValidateRequest) -> CheckoutValidateResponse:
        issues: list[str] = []
        cart = self._build_cart_response(user.id)

        if not cart.items:
            issues.append("Cart is empty")

        for line in cart.items:
            item = self._load_catalog()[line.item_id]
            if not item.in_stock:
                issues.append(f"{item.name} is out of stock")

        if payload.delivery_option not in {"standard", "express"}:
            issues.append("delivery_option must be one of: standard, express")

        payment_guard_issue = self._validate_payment_reference(user, payload.payment_method_reference)
        if payment_guard_issue:
            issues.append(payment_guard_issue)

        delivery_fee = 300 if payload.delivery_option == "standard" else 650
        return CheckoutValidateResponse(
            valid=len(issues) == 0,
            issues=issues,
            subtotal_cents=cart.subtotal_cents,
            delivery_fee_cents=delivery_fee,
            total_cents=cart.subtotal_cents + delivery_fee,
        )

    def authorize_payment_sim(self, user: User, payload: PaymentAuthorizeSimRequest) -> PaymentAuthorizeSimResponse:
        payment_guard_issue = self._validate_payment_reference(user, payload.payment_method_reference)
        if payment_guard_issue:
            raise ValidationAppError(payment_guard_issue)

        card_digits = self._normalize_card_digits(payload.payment_method_reference)
        if card_digits is None:
            raise ValidationAppError("Card number must contain 16 digits")

        # Deterministic simulation rule: card ending with 0000 is declined.
        if card_digits.endswith("0000"):
            return PaymentAuthorizeSimResponse(
                authorized=False,
                reason="Simulated payment authorization decline",
            )

        auth_seed = f"{card_digits}:{payload.amount_cents}:{payload.currency}"
        auth_code = hashlib.sha256(auth_seed.encode("utf-8")).hexdigest()[:12]
        return PaymentAuthorizeSimResponse(
            authorized=True,
            authorization_id=f"sim_auth_{auth_code}",
        )

    def create_order(
        self,
        user: User,
        payload: OrderCreateRequest,
        idempotency_key: str | None,
    ) -> OrderCreateResponse:
        if user.is_guest:
            raise ForbiddenError("Guest users must login/register before placing an order")

        if idempotency_key:
            previous = _IDEMPOTENT_ORDERS.get((user.id, idempotency_key))
            if previous is not None:
                return previous.model_copy(update={"idempotent_replay": True})

        checkout = self.validate_checkout(
            user,
            CheckoutValidateRequest(
                shipping_address=payload.shipping_address,
                delivery_option=payload.delivery_option,
                payment_method_reference=payload.payment_method_reference,
            ),
        )
        if not checkout.valid:
            raise ValidationAppError("Checkout validation failed", details={"issues": checkout.issues})

        payment = self.authorize_payment_sim(
            user,
            PaymentAuthorizeSimRequest(
                payment_method_reference=payload.payment_method_reference,
                amount_cents=checkout.total_cents,
            )
        )
        if not payment.authorized:
            raise ValidationAppError(payment.reason or "Payment authorization failed")

        created_at = datetime.now(UTC)
        eta_from, eta_to = self._build_eta_window(created_at, payload.delivery_option)
        order_id = f"ord_{uuid.uuid4().hex[:10]}"
        cart_snapshot = self._build_cart_response(user.id)
        ordered_items_summary = self._format_order_summary(cart_snapshot.items)
        order = self.order_repository.create(
            order_id=order_id,
            user_id=user.id,
            ordered_items_summary=ordered_items_summary,
            total_cents=checkout.total_cents,
            eta_from=eta_from,
            eta_to=eta_to,
        )
        _CARTS[user.id] = {}

        response = OrderCreateResponse(
            order_id=order.order_id,
            status=order.status,
            status_label=order.status_label,
            total_cents=checkout.total_cents,
            payment_authorization_id=payment.authorization_id or "sim_auth_unknown",
            created_at=order.created_at,
            idempotent_replay=False,
        )

        if idempotency_key:
            _IDEMPOTENT_ORDERS[(user.id, idempotency_key)] = response

        return response

    def get_order_lifecycle_sim(self, user: User, order_id: str, scenario_id: str) -> OrderLifecycleSimResponse:
        order = self.order_repository.get_by_order_id(order_id)
        if order is None:
            raise NotFoundError("Order not found")
        if order.user_id != user.id:
            raise ForbiddenError("Order does not belong to current user")

        seed = hashlib.sha256(f"{order_id}:{scenario_id}".encode("utf-8")).hexdigest()
        offset = int(seed[:2], 16) % 8
        base = order.created_at.astimezone(UTC)
        events = [
            OrderLifecycleEventResponse(timestamp=base + timedelta(minutes=2 + offset), event="accepted"),
            OrderLifecycleEventResponse(timestamp=base + timedelta(minutes=8 + offset), event="preparing"),
            OrderLifecycleEventResponse(timestamp=base + timedelta(minutes=18 + offset), event="driver_assigned"),
            OrderLifecycleEventResponse(timestamp=base + timedelta(minutes=30 + offset), event="arriving"),
        ]
        return OrderLifecycleSimResponse(order_id=order_id, scenario_id=scenario_id, events=events)

    def _build_cart_response(self, user_id: int) -> CartResponse:
        cart = _CARTS.setdefault(user_id, {})
        lines = []
        subtotal = 0
        for item_id, qty in cart.items():
            item = self._load_catalog().get(item_id)
            if item is None:
                continue
            line_total = item.price_cents * qty
            subtotal += line_total
            lines.append(
                {
                    "item_id": item.item_id,
                    "name": item.name,
                    "quantity": qty,
                    "unit_price_cents": item.price_cents,
                    "line_total_cents": line_total,
                    "currency": item.currency,
                }
            )

        return CartResponse(
            user_id=user_id,
            items=lines,
            subtotal_cents=subtotal,
            currency="USD",
        )

    def _validate_payment_reference(self, user: User, reference: str) -> str | None:
        if user.is_guest:
            return "Guest users cannot use checkout payment"

        if not user.demo_card_number:
            return "No demo card assigned to account"

        card_digits = self._normalize_card_digits(reference)
        if card_digits is None:
            return "Card number must contain 16 digits"

        assigned_digits = self._normalize_card_digits(user.demo_card_number)
        if assigned_digits is None:
            return "Assigned demo card is invalid"

        if card_digits != assigned_digits:
            return "Card number must match your assigned demo card"

        if not self._is_luhn_valid(card_digits):
            return "Card number failed validation"
        return None

    @staticmethod
    def _normalize_card_digits(value: str) -> str | None:
        digits = re.sub(r"\D", "", value or "")
        if len(digits) != 16:
            return None
        return digits

    @staticmethod
    def _is_luhn_valid(card_number: str) -> bool:
        digits = [int(ch) for ch in card_number]
        checksum = 0
        parity = len(digits) % 2
        for idx, digit in enumerate(digits):
            value = digit
            if idx % 2 == parity:
                value *= 2
                if value > 9:
                    value -= 9
            checksum += value
        return checksum % 10 == 0

    def _load_catalog(self) -> dict[str, CatalogItemResponse]:
        data = load_mock_data(self.settings.mock_data_path)

        restaurants_by_id = {int(item["id"]): item for item in data.get("restaurants", [])}
        catalog: dict[str, CatalogItemResponse] = {}

        for menu_item in data.get("menu_items", []):
            restaurant = restaurants_by_id.get(int(menu_item["restaurant_id"]))
            restaurant_name = restaurant["name"] if restaurant else "Unknown Restaurant"
            restaurant_open = bool(restaurant.get("is_open", True)) if restaurant else True
            restaurant_cuisine = str(restaurant["cuisine"]) if restaurant and restaurant.get("cuisine") else None
            restaurant_rating = float(restaurant["rating"]) if restaurant and restaurant.get("rating") is not None else None
            restaurant_delivery_time = (
                str(restaurant["delivery_time"]) if restaurant and restaurant.get("delivery_time") else None
            )
            restaurant_delivery_fee_cents = (
                int(float(restaurant["delivery_fee"]) * 100)
                if restaurant and restaurant.get("delivery_fee") is not None
                else None
            )
            catalog_item_id = f"item_{menu_item['id']}"
            catalog[catalog_item_id] = CatalogItemResponse(
                item_id=catalog_item_id,
                restaurant_id=int(menu_item["restaurant_id"]),
                restaurant_name=restaurant_name,
                restaurant_cuisine=restaurant_cuisine,
                restaurant_rating=restaurant_rating,
                restaurant_delivery_time=restaurant_delivery_time,
                restaurant_delivery_fee_cents=restaurant_delivery_fee_cents,
                name=str(menu_item["name"]),
                description=f"{menu_item['description']} | {restaurant_name} ({menu_item['category']})",
                image_url=str(menu_item["image"]) if menu_item.get("image") else None,
                price_cents=int(menu_item["price"]) * 100,
                in_stock=bool(menu_item.get("is_available", True)) and restaurant_open,
            )

        return catalog

    @staticmethod
    def _build_eta_window(created_at: datetime, delivery_option: str) -> tuple[datetime, datetime]:
        if delivery_option == "express":
            return created_at + timedelta(minutes=20), created_at + timedelta(minutes=30)
        return created_at + timedelta(minutes=35), created_at + timedelta(minutes=50)

    @staticmethod
    def _format_order_summary(lines: list[CartLineResponse]) -> str:
        if not lines:
            return "No items"

        parts: list[str] = []
        for line in lines:
            quantity = int(getattr(line, "quantity", 1))
            name = str(getattr(line, "name", "Item"))
            parts.append(f"{quantity}x {name}" if quantity > 1 else name)
        return ", ".join(parts)
