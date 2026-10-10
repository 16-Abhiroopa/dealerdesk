from django.db.models import Q
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from core.exceptions import NotFoundAppError, ValidationAppError
from core.pagination import StandardResultsSetPagination
from products.models import Product, Inventory
from products.serializers import (
    ProductSerializer,
    ProductCreateSerializer,
    ProductPatchSerializer,
)


class ProductListCreateView(APIView):
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        qs = Product.objects.select_related("inventory").all()

        search = request.query_params.get("search")
        if search:
            search = search.strip()
            qs = qs.filter(
                Q(sku__icontains=search)
                | Q(name__icontains=search)
                | Q(brand__icontains=search)
            )

        category = request.query_params.get("category")
        if category:
            qs = qs.filter(category=category.strip())

        vehicle = request.query_params.get("vehicle")
        if vehicle:
            qs = qs.filter(vehicle_fitment__icontains=vehicle.strip())

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = ProductSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = ProductCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)


class ProductDetailView(APIView):
    def get_object(self, sku: str) -> Product:
        try:
            return Product.objects.select_related("inventory").get(sku=sku)
        except Product.DoesNotExist:
            raise NotFoundAppError(f"Product with SKU '{sku}' not found.")

    def get(self, request, sku: str):
        product = self.get_object(sku)
        return Response(ProductSerializer(product).data)

    def patch(self, request, sku: str):
        product = self.get_object(sku)
        if "sku" in request.data and request.data["sku"] != sku:
            raise ValidationAppError("SKU cannot be changed.")

        serializer = ProductPatchSerializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        return Response(ProductSerializer(product).data)


class InventoryUpdateView(APIView):
    def put(self, request, sku: str):
        try:
            product = Product.objects.get(sku=sku)
        except Product.DoesNotExist:
            raise NotFoundAppError(f"Product with SKU '{sku}' not found.")

        data = request.data
        if not isinstance(data, dict) or "quantity" not in data:
            raise ValidationAppError("Quantity field is required.")

        quantity = data["quantity"]
        if isinstance(quantity, bool) or not isinstance(quantity, int):
            raise ValidationAppError("Quantity must be an integer.")
        if quantity < 0:
            raise ValidationAppError("Quantity must be greater than or equal to 0.")

        inv, _ = Inventory.objects.get_or_create(product=product)
        inv.quantity = quantity
        inv.save(update_fields=["quantity", "updated_at"])

        return Response({"sku": sku, "quantity": quantity}, status=status.HTTP_200_OK)
