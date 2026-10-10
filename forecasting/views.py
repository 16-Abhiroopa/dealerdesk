from rest_framework.views import APIView
from rest_framework.response import Response


class ForecastSkuView(APIView):
    def get(self, request, sku: str):
        return Response({"sku": sku, "forecast": []})


class ReorderSuggestionsView(APIView):
    def get(self, request):
        return Response({"results": []})
