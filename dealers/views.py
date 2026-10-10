from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from core.exceptions import NotFoundAppError
from core.pagination import StandardResultsSetPagination
from dealers.models import Dealer
from dealers.serializers import DealerSerializer, DealerCreateSerializer


class DealerListCreateView(APIView):
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        qs = Dealer.objects.all()
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = DealerSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = DealerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dealer = serializer.save()
        return Response(DealerSerializer(dealer).data, status=status.HTTP_201_CREATED)


class DealerDetailView(APIView):
    def get(self, request, pk: int):
        try:
            dealer = Dealer.objects.get(pk=pk)
        except Dealer.DoesNotExist:
            raise NotFoundAppError(f"Dealer with id {pk} not found.")
        return Response(DealerSerializer(dealer).data)
