from decimal import Decimal
from rest_framework import serializers
from core.exceptions import DuplicateAppError, ValidationAppError
from core.utils import format_money, is_valid_price
from products.models import Product, Inventory


class ProductSerializer(serializers.ModelSerializer):
    price = serializers.SerializerMethodField()
    stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "sku",
            "name",
            "category",
            "brand",
            "vehicle_fitment",
            "price",
            "stock",
            "description",
        ]

    def get_price(self, obj) -> str:
        return format_money(obj.price)

    def get_stock(self, obj) -> int:
        return obj.stock


class ProductCreateSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(required=True, validators=[])
    price = serializers.CharField()

    class Meta:
        model = Product
        fields = [
            "sku",
            "name",
            "category",
            "brand",
            "vehicle_fitment",
            "price",
            "description",
        ]

    def validate_sku(self, value):
        sku = value.strip()
        if not sku:
            raise ValidationAppError("SKU cannot be empty.")
        if Product.objects.filter(sku=sku).exists():
            raise DuplicateAppError(f"Product with SKU '{sku}' already exists.")
        return sku

    def validate_price(self, value):
        if not is_valid_price(value):
            raise ValidationAppError("Price must be a positive number with at most 2 decimal places.")
        return Decimal(str(value))

    def create(self, validated_data):
        product = Product.objects.create(**validated_data)
        # Create corresponding Inventory row with starting stock 0
        Inventory.objects.create(product=product, quantity=0)
        return product


class ProductPatchSerializer(serializers.ModelSerializer):
    price = serializers.CharField(required=False)

    class Meta:
        model = Product
        fields = [
            "name",
            "category",
            "brand",
            "vehicle_fitment",
            "price",
            "description",
        ]

    def validate_price(self, value):
        if value is not None and not is_valid_price(value):
            raise ValidationAppError("Price must be a positive number with at most 2 decimal places.")
        return Decimal(str(value))
