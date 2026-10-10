from decimal import Decimal
from django.db import models
from django.db.models import Q
from dealers.models import Dealer
from products.models import Product


class Order(models.Model):
    STATUS_CHOICES = [
        ("DRAFT", "DRAFT"),
        ("CONFIRMED", "CONFIRMED"),
        ("DISPATCHED", "DISPATCHED"),
        ("DELIVERED", "DELIVERED"),
        ("CANCELLED", "CANCELLED"),
    ]

    order_number = models.CharField(max_length=64, unique=True, db_index=True)
    dealer = models.ForeignKey(Dealer, on_delete=models.PROTECT, related_name="orders")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT", db_index=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.order_number} ({self.status})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    line_tax = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gte=1),
                name="order_item_quantity_gte_1",
            ),
            models.UniqueConstraint(
                fields=["order", "product"],
                name="unique_order_product",
            ),
        ]

    def __str__(self):
        return f"{self.order.order_number} - {self.product.sku} x {self.quantity}"


class OrderSequence(models.Model):
    """Atomic daily counter for order numbers: ORD-YYYYMMDD-NNNN in Asia/Kolkata timezone."""
    date = models.DateField(unique=True, db_index=True)
    last_number = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.date}: {self.last_number}"


class IdempotencyKey(models.Model):
    """Track Idempotency-Key headers and request payload hash to prevent duplicate orders."""
    key = models.CharField(max_length=255, unique=True, db_index=True)
    request_hash = models.CharField(max_length=64)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="idempotency_keys")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.key} -> {self.order.order_number}"
