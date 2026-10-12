"""Order management service encapsulating all business logic and invariants.

Shared between API views and the Dealer Assistant.
Invariants:
- All-or-nothing stock deduction under deterministic product-id row locks.
- Exact paise calculation with ROUND_HALF_UP per line.
- Concurrency-safe atomic order numbering ORD-YYYYMMDD-NNNN.
- Strict state machine transitions.
- Idempotency via request payload hash.
"""
from decimal import Decimal
import hashlib
from datetime import datetime
import zoneinfo
from django.db import transaction
from django.utils import timezone
from core.exceptions import (
    ValidationAppError,
    NotFoundAppError,
    InsufficientStockAppError,
    InvalidTransitionAppError,
    OrderLockedAppError,
    IdempotencyConflictAppError,
)
from core.utils import round_half_up
from dealers.models import Dealer
from products.models import Product, Inventory
from orders.models import Order, OrderItem, OrderSequence, IdempotencyKey

KOLKATA_TZ = zoneinfo.ZoneInfo("Asia/Kolkata")


def validate_item_quantity(qty):
    """Validate that quantity is strictly an integer >= 1 (no floats, bools, strings, null)."""
    if isinstance(qty, bool) or not isinstance(qty, int):
        raise ValidationAppError("Item quantity must be a positive integer.")
    if qty < 1:
        raise ValidationAppError("Item quantity must be at least 1.")
    return qty


def get_dealer_available_credit(dealer: Dealer, exclude_order_id: int = None) -> tuple[Decimal, Decimal]:
    """Calculate (outstanding_committed_orders, available_credit) for a dealer."""
    if dealer.credit_limit <= Decimal("0.00"):
        return Decimal("0.00"), Decimal("999999999.00")
    active_qs = Order.objects.filter(
        dealer=dealer,
        status__in=["CONFIRMED", "DISPATCHED"],
    )
    if exclude_order_id:
        active_qs = active_qs.exclude(id=exclude_order_id)
    outstanding = sum((o.grand_total for o in active_qs), Decimal("0.00"))
    available_credit = max(Decimal("0.00"), dealer.credit_limit - outstanding)
    return outstanding, available_credit


def validate_dealer_credit(dealer: Dealer, grand_total: Decimal, exclude_order_id: int = None):
    """Enforce that order grand_total does not exceed available credit limit."""
    if dealer.credit_limit <= Decimal("0.00"):
        return
    outstanding, available = get_dealer_available_credit(dealer, exclude_order_id=exclude_order_id)
    if grand_total > available:
        raise ValidationAppError(
            f"Credit limit exceeded for {dealer.name}. "
            f"Available credit: ₹{available:.2f} (Credit Limit: ₹{dealer.credit_limit:.2f}, "
            f"Outstanding Orders: ₹{outstanding:.2f}). Order total: ₹{grand_total:.2f}."
        )


def get_next_order_number() -> str:
    """Generate the next unique order number for today in Asia/Kolkata timezone."""
    now_ist = datetime.now(KOLKATA_TZ)
    today = now_ist.date()

    seq, _ = OrderSequence.objects.select_for_update().get_or_create(date=today)
    seq.last_number += 1
    seq.save(update_fields=["last_number"])

    date_str = today.strftime("%Y%m%d")
    return f"ORD-{date_str}-{seq.last_number:04d}"


def calculate_line_item(product: Product, quantity: int):
    """Calculate unit_price, line_subtotal, line_tax (18% ROUND_HALF_UP), and line_total."""
    unit_price = product.price
    line_subtotal = round_half_up(unit_price * Decimal(quantity))
    line_tax = round_half_up(line_subtotal * Decimal("0.18"))
    line_total = line_subtotal + line_tax
    return {
        "product": product,
        "quantity": quantity,
        "unit_price": unit_price,
        "line_subtotal": line_subtotal,
        "line_tax": line_tax,
        "line_total": line_total,
    }


def create_draft_order(dealer_id: int, items_data: list, idempotency_key: str = None, raw_body_bytes: bytes = None) -> tuple[Order, bool]:
    """Create a DRAFT order with transactional validation and idempotency.

    Returns (order, created_bool).
    """
    if not isinstance(dealer_id, int):
        raise ValidationAppError("Valid dealer_id integer is required.")

    if not items_data or not isinstance(items_data, list):
        raise ValidationAppError("Order must contain at least one item.")

    with transaction.atomic():
        # Handle idempotency first if key is provided
        if idempotency_key:
            req_hash = hashlib.sha256(raw_body_bytes or b"").hexdigest()
            existing_idemp = IdempotencyKey.objects.select_for_update().filter(key=idempotency_key).first()
            if existing_idemp:
                if existing_idemp.request_hash == req_hash:
                    return existing_idemp.order, False
                else:
                    raise IdempotencyConflictAppError("Idempotency-Key reused with different request payload.")

        try:
            dealer = Dealer.objects.get(id=dealer_id)
        except Dealer.DoesNotExist:
            raise ValidationAppError(f"Dealer with id {dealer_id} does not exist.")

        # Check duplicate SKUs in items
        seen_skus = set()
        validated_items = []
        for item in items_data:
            if not isinstance(item, dict):
                raise ValidationAppError("Each item must be an object with sku and quantity.")
            sku = item.get("sku")
            if not sku or not isinstance(sku, str):
                raise ValidationAppError("Each item must specify a valid sku.")
            if sku in seen_skus:
                raise ValidationAppError(f"Duplicate SKU '{sku}' found in order items.")
            seen_skus.add(sku)

            qty = validate_item_quantity(item.get("quantity"))
            validated_items.append((sku, qty))

        # Check all products exist
        products_by_sku = {
            p.sku: p for p in Product.objects.filter(sku__in=seen_skus)
        }
        for sku, _ in validated_items:
            if sku not in products_by_sku:
                raise ValidationAppError(f"Product with SKU '{sku}' does not exist.")

        # Calculate line items and totals
        line_items = []
        subtotal = Decimal("0.00")
        tax_total = Decimal("0.00")

        for sku, qty in validated_items:
            product = products_by_sku[sku]
            calcs = calculate_line_item(product, qty)
            line_items.append(calcs)
            subtotal += calcs["line_subtotal"]
            tax_total += calcs["line_tax"]

        grand_total = subtotal + tax_total
        validate_dealer_credit(dealer, grand_total)
        order_number = get_next_order_number()

        order = Order.objects.create(
            order_number=order_number,
            dealer=dealer,
            status="DRAFT",
            subtotal=subtotal,
            tax_total=tax_total,
            grand_total=grand_total,
        )

        order_items_to_create = [
            OrderItem(
                order=order,
                product=item["product"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                line_subtotal=item["line_subtotal"],
                line_tax=item["line_tax"],
                line_total=item["line_total"],
            )
            for item in line_items
        ]
        OrderItem.objects.bulk_create(order_items_to_create)

        if idempotency_key:
            IdempotencyKey.objects.create(
                key=idempotency_key,
                request_hash=req_hash,
                order=order,
            )

        return order, True


def update_draft_order(order_number: str, items_data: list) -> Order:
    """Replace all items of an existing DRAFT order."""
    if not items_data or not isinstance(items_data, list):
        raise ValidationAppError("Order must contain at least one item.")

    with transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(order_number=order_number)
        except Order.DoesNotExist:
            raise NotFoundAppError(f"Order '{order_number}' not found.")

        if order.status != "DRAFT":
            raise OrderLockedAppError("Order cannot be modified because it is not in DRAFT status.")

        seen_skus = set()
        validated_items = []
        for item in items_data:
            if not isinstance(item, dict):
                raise ValidationAppError("Each item must be an object with sku and quantity.")
            sku = item.get("sku")
            if not sku or not isinstance(sku, str):
                raise ValidationAppError("Each item must specify a valid sku.")
            if sku in seen_skus:
                raise ValidationAppError(f"Duplicate SKU '{sku}' found in order items.")
            seen_skus.add(sku)

            qty = validate_item_quantity(item.get("quantity"))
            validated_items.append((sku, qty))

        products_by_sku = {
            p.sku: p for p in Product.objects.filter(sku__in=seen_skus)
        }
        for sku, _ in validated_items:
            if sku not in products_by_sku:
                raise ValidationAppError(f"Product with SKU '{sku}' does not exist.")

        # Delete existing items
        order.items.all().delete()

        line_items = []
        subtotal = Decimal("0.00")
        tax_total = Decimal("0.00")

        for sku, qty in validated_items:
            product = products_by_sku[sku]
            calcs = calculate_line_item(product, qty)
            line_items.append(calcs)
            subtotal += calcs["line_subtotal"]
            tax_total += calcs["line_tax"]

        grand_total = subtotal + tax_total
        validate_dealer_credit(order.dealer, grand_total, exclude_order_id=order.id)

        order.subtotal = subtotal
        order.tax_total = tax_total
        order.grand_total = grand_total
        order.save(update_fields=["subtotal", "tax_total", "grand_total", "updated_at"])

        order_items_to_create = [
            OrderItem(
                order=order,
                product=item["product"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                line_subtotal=item["line_subtotal"],
                line_tax=item["line_tax"],
                line_total=item["line_total"],
            )
            for item in line_items
        ]
        OrderItem.objects.bulk_create(order_items_to_create)

        return order


def confirm_order(order_number: str) -> Order:
    """Transition DRAFT -> CONFIRMED, atomically validating and deducting stock."""
    with transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(order_number=order_number)
        except Order.DoesNotExist:
            raise NotFoundAppError(f"Order '{order_number}' not found.")

        if order.status != "DRAFT":
            raise InvalidTransitionAppError(f"Cannot confirm order in {order.status} status.")

        validate_dealer_credit(order.dealer, order.grand_total, exclude_order_id=order.id)

        items = list(order.items.select_related("product").all())
        # Sort product IDs to prevent deadlocks across concurrent confirms
        product_ids = sorted([item.product_id for item in items])

        inventories = {
            inv.product_id: inv
            for inv in Inventory.objects.select_for_update().filter(product_id__in=product_ids).order_by("product_id")
        }

        short_lines = []
        error_messages = []
        for item in items:
            inv = inventories.get(item.product_id)
            available = inv.quantity if inv else 0
            if item.quantity > available:
                short_lines.append({
                    "sku": item.product.sku,
                    "requested": item.quantity,
                    "available": available,
                })
                error_messages.append(
                    f"Insufficient stock for {item.product.name}. Available: {available}, Requested: {item.quantity}"
                )

        if short_lines:
            raise InsufficientStockAppError(
                message=". ".join(error_messages),
                details=short_lines,
            )

        # Deduct stock for all lines
        for item in items:
            inv = inventories[item.product_id]
            inv.quantity -= item.quantity
            inv.save(update_fields=["quantity", "updated_at"])

        order.status = "CONFIRMED"
        order.save(update_fields=["status", "updated_at"])

        return order


def dispatch_order(order_number: str) -> Order:
    """Transition CONFIRMED -> DISPATCHED."""
    with transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(order_number=order_number)
        except Order.DoesNotExist:
            raise NotFoundAppError(f"Order '{order_number}' not found.")

        if order.status != "CONFIRMED":
            raise InvalidTransitionAppError(f"Cannot dispatch order in {order.status} status.")

        order.status = "DISPATCHED"
        order.save(update_fields=["status", "updated_at"])
        return order


def deliver_order(order_number: str) -> Order:
    """Transition DISPATCHED -> DELIVERED."""
    with transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(order_number=order_number)
        except Order.DoesNotExist:
            raise NotFoundAppError(f"Order '{order_number}' not found.")

        if order.status != "DISPATCHED":
            raise InvalidTransitionAppError(f"Cannot deliver order in {order.status} status.")

        order.status = "DELIVERED"
        order.save(update_fields=["status", "updated_at"])
        return order


def cancel_order(order_number: str) -> Order:
    """Cancel DRAFT or CONFIRMED order, restoring stock exactly once if CONFIRMED."""
    with transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(order_number=order_number)
        except Order.DoesNotExist:
            raise NotFoundAppError(f"Order '{order_number}' not found.")

        if order.status not in ("DRAFT", "CONFIRMED"):
            raise InvalidTransitionAppError(f"Cannot cancel order in {order.status} status.")

        if order.status == "CONFIRMED":
            items = list(order.items.select_related("product").all())
            product_ids = sorted([item.product_id for item in items])
            inventories = {
                inv.product_id: inv
                for inv in Inventory.objects.select_for_update().filter(product_id__in=product_ids).order_by("product_id")
            }
            for item in items:
                inv = inventories.get(item.product_id)
                if inv:
                    inv.quantity += item.quantity
                    inv.save(update_fields=["quantity", "updated_at"])

        order.status = "CANCELLED"
        order.save(update_fields=["status", "updated_at"])
        return order
