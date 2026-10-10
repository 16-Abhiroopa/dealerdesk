from django.db import models
from django.db.models import Q


class Product(models.Model):
    sku = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=100, db_index=True)
    brand = models.CharField(max_length=100, db_index=True)
    vehicle_fitment = models.CharField(max_length=255, db_index=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sku"]
        constraints = [
            models.CheckConstraint(
                condition=Q(price__gt=0),
                name="product_price_positive",
            )
        ]
        indexes = [
            models.Index(fields=["category"]),
            models.Index(fields=["vehicle_fitment"]),
            models.Index(fields=["brand"]),
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return f"{self.sku} - {self.name}"

    @property
    def stock(self) -> int:
        try:
            return self.inventory.quantity
        except Exception:
            return 0


class Inventory(models.Model):
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="inventory",
        primary_key=True,
    )
    quantity = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gte=0),
                name="inventory_quantity_non_negative",
            )
        ]

    def __str__(self):
        return f"{self.product_id}: {self.quantity} units"
