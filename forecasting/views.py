import os
import csv
import math
from functools import lru_cache
from typing import Dict, List, Any
import numpy as np
import pandas as pd
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response

from core.exceptions import NotFoundAppError
from products.models import Product


def _get_forecast_data() -> Dict[str, List[Dict[str, Any]]]:
    """Load and parse ml/forecast.csv into a dictionary keyed by SKU."""
    forecast_path = os.path.join(settings.BASE_DIR, "ml", "forecast.csv")
    if not os.path.exists(forecast_path):
        from ml.train_and_forecast import train_and_generate_forecast
        train_and_generate_forecast(
            data_dir=os.path.join(settings.BASE_DIR, "data"),
            output_path=forecast_path,
        )

    forecast_by_sku: Dict[str, List[Dict[str, Any]]] = {}
    with open(forecast_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sku = row["sku"]
            entry = {
                "week_start": row["week_start"],
                "forecast_units": float(row["forecast_units"]),
            }
            if sku not in forecast_by_sku:
                forecast_by_sku[sku] = []
            forecast_by_sku[sku].append(entry)

    # Sort each SKU's forecast chronologically
    for sku in forecast_by_sku:
        forecast_by_sku[sku].sort(key=lambda x: x["week_start"])

    return forecast_by_sku


@lru_cache(maxsize=1)
def _get_lead_times_and_sigmas():
    """Load lead times and compute sample standard deviation sigma from sales_history.csv."""
    data_dir = os.path.join(settings.BASE_DIR, "data")
    lead_path = os.path.join(data_dir, "lead_times.csv")
    sales_path = os.path.join(data_dir, "sales_history.csv")

    lead_df = pd.read_csv(lead_path)
    sales_df = pd.read_csv(sales_path)
    sales_df["week_start"] = pd.to_datetime(sales_df["week_start"])

    sku_lead_times: Dict[str, int] = {}
    sku_sigmas: Dict[str, float] = {}

    for _, row in lead_df.iterrows():
        sku = row["sku"]
        L = int(row["lead_time_weeks"])
        sku_lead_times[sku] = L

        s_hist = sales_df[sales_df["sku"] == sku].sort_values("week_start")
        recent_12 = s_hist["units_sold"].iloc[-12:].values
        if len(recent_12) > 1:
            sigma = float(np.std(recent_12, ddof=1))
        else:
            sigma = 0.0
        sku_sigmas[sku] = sigma

    return list(lead_df["sku"]), sku_lead_times, sku_sigmas


class ForecastSkuView(APIView):
    """GET /api/forecast/{sku}/ - Returns 4-week forecast for a specific SKU."""

    def get(self, request, sku: str):
        forecast_data = _get_forecast_data()
        if sku not in forecast_data:
            raise NotFoundAppError(f"Forecast for SKU '{sku}' not found.")

        return Response({
            "sku": sku,
            "forecast": forecast_data[sku],
        })


class ReorderSuggestionsView(APIView):
    """GET /api/reorder-suggestions/ - Returns reorder point calculations for all 40 forecast SKUs."""

    def get(self, request):
        forecast_data = _get_forecast_data()
        sku_order, lead_times, sigmas = _get_lead_times_and_sigmas()

        # Fetch current live stock for all forecast SKUs
        products = Product.objects.filter(sku__in=sku_order).select_related("inventory")
        stock_by_sku = {p.sku: p.stock for p in products}

        results = []
        for sku in sku_order:
            current_stock = stock_by_sku.get(sku, 0)
            L = lead_times.get(sku, 1)
            sigma = sigmas.get(sku, 0.0)

            # lead_time_demand = sum of forecast_units for the first L forecast weeks
            sku_forecast = forecast_data.get(sku, [])
            ltd_sum = sum(week["forecast_units"] for week in sku_forecast[:L])
            lead_time_demand = round(float(ltd_sum), 1)

            # safety_stock = ceil(1.65 * sigma * sqrt(L))
            safety_stock = int(math.ceil(1.65 * sigma * math.sqrt(L)))

            # reorder_point = lead_time_demand + safety_stock
            reorder_point = round(lead_time_demand + safety_stock, 1)

            # reorder_qty = max(0, ceil(reorder_point - current_stock))
            reorder_qty = max(0, int(math.ceil(reorder_point - current_stock)))

            results.append({
                "sku": sku,
                "current_stock": current_stock,
                "lead_time_weeks": L,
                "lead_time_demand": lead_time_demand,
                "safety_stock": safety_stock,
                "reorder_point": reorder_point,
                "reorder_qty": reorder_qty,
            })

        return Response({"results": results})
