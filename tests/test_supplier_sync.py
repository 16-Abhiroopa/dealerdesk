import pytest
from unittest.mock import patch, MagicMock
from rest_framework.test import APIClient
from products.models import Product, Inventory


@pytest.mark.django_db
def test_supplier_sync_success(settings):
    settings.SUPPLIER_API_URL = "http://mock-supplier.internal"
    settings.SUPPLIER_API_KEY = "test-secret-key"

    client = APIClient()

    # Pre-existing product
    existing_p = Product.objects.create(
        sku="TEST-SYNC-1",
        name="Old Name",
        category="Brakes",
        brand="Endurance",
        vehicle_fitment="Universal",
        price="100.00",
        description="Old desc",
    )
    Inventory.objects.create(product=existing_p, quantity=42)

    # Mock response from supplier: 2 items
    # Item 1: updates TEST-SYNC-1
    # Item 2: new product TEST-SYNC-2
    # Item 3: invalid price -> rejected
    mock_page = {
        "items": [
            {
                "supplier_sku": "SUP-1",
                "sku": "TEST-SYNC-1",
                "name": "New Updated Name",
                "category": "Brakes",
                "brand": "Endurance",
                "vehicle_fitment": "Universal",
                "price": "120.00",
                "description": "Updated desc",
                "supplier_stock": 999,
                "updated_at": "2026-10-10T12:00:00Z",
            },
            {
                "supplier_sku": "SUP-2",
                "sku": "TEST-SYNC-2",
                "name": "Brand New Part",
                "category": "Filters",
                "brand": "Mahle",
                "vehicle_fitment": "KTM Duke 390",
                "price": "250.50",
                "description": "Fresh part",
                "supplier_stock": 50,
                "updated_at": "2026-10-10T12:00:00Z",
            },
            {
                "supplier_sku": "SUP-3",
                "sku": "TEST-SYNC-INVALID",
                "name": "Broken Part",
                "price": "-5.00",  # invalid negative price
                "updated_at": "2026-10-10T12:00:00Z",
            },
        ],
        "next_cursor": None,
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_page

    with patch("requests.get", return_value=mock_resp):
        res = client.post("/api/sync/supplier/")
        assert res.status_code == 200
        data = res.json()
        assert data["created"] == 1
        assert data["updated"] == 1
        assert data["unchanged"] == 0
        assert len(data["rejected"]) == 1
        assert data["rejected"][0]["supplier_sku"] == "SUP-3"
        assert data["pages_fetched"] == 1
        assert data["requests_made"] == 1

    # Verify database updates
    existing_p.refresh_from_db()
    assert existing_p.name == "New Updated Name"
    assert str(existing_p.price) == "120.00"
    # Verify local stock was NOT overwritten by supplier_stock (999)
    assert existing_p.stock == 42

    new_p = Product.objects.get(sku="TEST-SYNC-2")
    assert new_p.name == "Brand New Part"
    # Newly created product starts with stock 0
    assert new_p.stock == 0


@pytest.mark.django_db
def test_supplier_sync_failure_returns_502(settings):
    settings.SUPPLIER_API_URL = "http://mock-supplier.internal"
    settings.SUPPLIER_API_KEY = "test-secret-key"

    client = APIClient()

    # Mock 500 error on all attempts
    mock_resp = MagicMock()
    mock_resp.status_code = 500

    with patch("requests.get", return_value=mock_resp):
        res = client.post("/api/sync/supplier/")
        assert res.status_code == 502
        data = res.json()
        assert "error" in data
        assert data["error"]["code"] == "SUPPLIER_UNAVAILABLE"
