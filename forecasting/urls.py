from django.urls import path
from forecasting.views import ForecastSkuView, ReorderSuggestionsView

urlpatterns = [
    path("forecast/<str:sku>/", ForecastSkuView.as_view(), name="forecast-sku"),
    path("reorder-suggestions/", ReorderSuggestionsView.as_view(), name="reorder-suggestions"),
]
