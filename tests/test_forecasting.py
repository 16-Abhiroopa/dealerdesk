import math
import pytest
from rest_framework.test import APIClient
from products.models import Product, Inventory
from forecasting.views import _get_forecast_data, _get_lead_times_and_sigmas


@pytest.mark.django_db
def test_forecast_sku_success():
    client = APIClient()
    # Pick a known SKU from lead_times.csv
    sku = "FIL-1016"
    res = client.get(f"/api/forecast/{sku}/")
    assert res.status_code == 200
    data = res.json()

    assert data["sku"] == sku
    assert "forecast" in data
    assert len(data["forecast"]) == 4
    expected_weeks = ["2026-09-28", "2026-10-05", "2026-10-12", "2026-10-19"]
    actual_weeks = [item["week_start"] for item in data["forecast"]]
    assert actual_weeks == expected_weeks
    for item in data["forecast"]:
        assert isinstance(item["forecast_units"], (int, float))
        assert item["forecast_units"] >= 0


@pytest.mark.django_db
def test_forecast_sku_not_found():
    client = APIClient()
    res = client.get("/api/forecast/NON-EXISTENT-SKU/")
    assert res.status_code == 404
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"


@pytest.mark.django_db
def test_reorder_suggestions_all_40_skus():
    client = APIClient()
    res = client.get("/api/reorder-suggestions/")
    assert res.status_code == 200
    data = res.json()
    assert "results" in data
    results = data["results"]
    assert len(results) == 40

    required_keys = (
        "sku",
        "current_stock",
        "lead_time_weeks",
        "lead_time_demand",
        "safety_stock",
        "reorder_point",
        "reorder_qty",
    )
    for entry in results:
        for k in required_keys:
            assert k in entry, f"Missing key {k} in reorder entry"
        assert isinstance(entry["current_stock"], int)
        assert isinstance(entry["lead_time_weeks"], int)
        assert entry["lead_time_weeks"] in (1, 2, 3, 4)
        assert isinstance(entry["lead_time_demand"], (int, float))
        assert isinstance(entry["safety_stock"], int)
        assert isinstance(entry["reorder_point"], (int, float))
        assert isinstance(entry["reorder_qty"], int)
        assert entry["reorder_qty"] >= 0


@pytest.mark.django_db
def test_reorder_suggestions_formula_and_live_stock_update():
    client = APIClient()
    sku = "FIL-1016"

    # Ensure product exists with stock = 10
    product, _ = Product.objects.get_or_create(
        sku=sku,
        defaults={
            "name": "Filter 1016",
            "category": "Filters",
            "brand": "Mahle",
            "vehicle_fitment": "Universal",
            "price": "500.00",
        },
    )
    Inventory.objects.update_or_create(product=product, defaults={"quantity": 10})

    res1 = client.get("/api/reorder-suggestions/")
    assert res1.status_code == 200
    entry1 = next(item for item in res1.json()["results"] if item["sku"] == sku)

    assert entry1["current_stock"] == 10
    # Verify exact math
    expected_rp = round(entry1["lead_time_demand"] + entry1["safety_stock"], 1)
    assert entry1["reorder_point"] == expected_rp
    expected_qty_1 = max(0, math.ceil(expected_rp - 10))
    assert entry1["reorder_qty"] == expected_qty_1

    # Now update stock live to a large quantity (e.g. 500)
    Inventory.objects.update_or_create(product=product, defaults={"quantity": 500})
    res2 = client.get("/api/reorder-suggestions/")
    assert res2.status_code == 200
    entry2 = next(item for item in res2.json()["results"] if item["sku"] == sku)

    assert entry2["current_stock"] == 500
    # Reorder qty should drop to 0 because current stock > reorder point
    assert entry2["reorder_qty"] == 0
