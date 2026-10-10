import pytest
from rest_framework.test import APIClient
from dealers.models import Dealer
from products.models import Product, Inventory


@pytest.mark.django_db
def test_inventory_update_and_validation():
    client = APIClient()
    p = Product.objects.create(
        sku="INV-TEST",
        name="Test Filter",
        category="Filters",
        brand="Mahle",
        vehicle_fitment="Universal",
        price="250.00",
    )
    Inventory.objects.create(product=p, quantity=5)

    # Valid update
    res = client.put("/api/inventory/INV-TEST/", {"quantity": 40, "reason": "Restock"}, format="json")
    assert res.status_code == 200
    assert res.json() == {"sku": "INV-TEST", "quantity": 40}

    # Verify reflected in product detail
    res_p = client.get("/api/products/INV-TEST/")
    assert res_p.status_code == 200
    assert res_p.json()["stock"] == 40

    # Negative quantity
    res_neg = client.put("/api/inventory/INV-TEST/", {"quantity": -5}, format="json")
    assert res_neg.status_code == 400
    assert res_neg.json()["error"]["code"] == "VALIDATION_ERROR"

    # Non-integer / boolean quantity
    res_bool = client.put("/api/inventory/INV-TEST/", {"quantity": True}, format="json")
    assert res_bool.status_code == 400
    assert res_bool.json()["error"]["code"] == "VALIDATION_ERROR"

    # Unknown SKU
    res_404 = client.put("/api/inventory/UNKNOWN-SKU/", {"quantity": 10}, format="json")
    assert res_404.status_code == 404
    assert res_404.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.django_db
def test_dealer_crud_and_duplicates():
    client = APIClient()
    # Create dealer
    payload = {
        "dealer_code": "DLR-999",
        "name": "Super Riders",
        "city": "Bengaluru",
        "phone": "9876543210",
        "email": "super@riders.in",
        "gstin": "29AABC1234F1Z5",
        "credit_limit": "200000.00",
    }
    res = client.post("/api/dealers/", payload, format="json")
    assert res.status_code == 201
    d_id = res.json()["id"]

    # Duplicate dealer_code
    res_dup = client.post("/api/dealers/", payload, format="json")
    assert res_dup.status_code == 409
    assert res_dup.json()["error"]["code"] == "DUPLICATE"

    # Get dealer detail
    res_get = client.get(f"/api/dealers/{d_id}/")
    assert res_get.status_code == 200
    assert res_get.json()["dealer_code"] == "DLR-999"

    # Unknown dealer
    res_404 = client.get("/api/dealers/999999/")
    assert res_404.status_code == 404
    assert res_404.json()["error"]["code"] == "NOT_FOUND"
