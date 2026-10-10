from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from core.exceptions import NotFoundAppError, ValidationAppError
from core.pagination import StandardResultsSetPagination
from orders.models import Order
from orders.serializers import OrderSerializer
from orders import services


class OrderListCreateView(APIView):
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        qs = Order.objects.select_related("dealer").prefetch_related("items__product").all()

        dealer_id = request.query_params.get("dealer_id")
        if dealer_id:
            try:
                qs = qs.filter(dealer_id=int(dealer_id))
            except ValueError:
                raise ValidationAppError("dealer_id query param must be an integer.")

        order_status = request.query_params.get("status")
        if order_status:
            qs = qs.filter(status=order_status.strip().upper())

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = OrderSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        data = request.data
        if not isinstance(data, dict):
            raise ValidationAppError("Request body must be a JSON object.")

        dealer_id = data.get("dealer_id")
        items = data.get("items")

        idempotency_key = request.headers.get("Idempotency-Key") or request.META.get("HTTP_IDEMPOTENCY_KEY")
        raw_body = request.body

        order, created = services.create_draft_order(
            dealer_id=dealer_id,
            items_data=items,
            idempotency_key=idempotency_key,
            raw_body_bytes=raw_body,
        )

        serializer = OrderSerializer(order)
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(serializer.data, status=status_code)


class OrderDetailView(APIView):
    def get(self, request, order_number: str):
        try:
            order = (
                Order.objects.select_related("dealer")
                .prefetch_related("items__product")
                .get(order_number=order_number)
            )
        except Order.DoesNotExist:
            raise NotFoundAppError(f"Order '{order_number}' not found.")

        return Response(OrderSerializer(order).data)

    def put(self, request, order_number: str):
        data = request.data
        if not isinstance(data, dict) or "items" not in data:
            raise ValidationAppError("Items list is required to update order.")

        order = services.update_draft_order(order_number, data["items"])
        return Response(OrderSerializer(order).data)


class OrderConfirmView(APIView):
    def post(self, request, order_number: str):
        order = services.confirm_order(order_number)
        return Response(OrderSerializer(order).data)


class OrderDispatchView(APIView):
    def post(self, request, order_number: str):
        order = services.dispatch_order(order_number)
        return Response(OrderSerializer(order).data)


class OrderDeliverView(APIView):
    def post(self, request, order_number: str):
        order = services.deliver_order(order_number)
        return Response(OrderSerializer(order).data)


class OrderCancelView(APIView):
    def post(self, request, order_number: str):
        order = services.cancel_order(order_number)
        return Response(OrderSerializer(order).data)
