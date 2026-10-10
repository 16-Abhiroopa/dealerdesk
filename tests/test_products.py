import pytest
from rest_framework.test import APIClient
from products.models import Product, Inventory


@pytest.mark.django_db
def test_products_list_and_filters():
    client = APIClient()
    p1 = Product.objects.create(
        sku="TEST-001",
        name="High Performance Brake Pad",
        category="Brakes",
        brand="Brembo",
        vehicle_fitment="KTM Duke 390",
        price="1500.50",
    )
    Inventory.objects.create(product=p1, quantity=10)

    p2 = Product.objects.create(
        sku="TEST-002",
        name="Engine Oil 1L",
        category="Engine & Oils",
        brand="Motul",
        vehicle_fitment="Universal",
        price="850.00",
    )
    Inventory.objects.create(product=p2, quantity=25)

    # List endpoint pagination
    res = client.get("/api/products/?page_size=1")
    assert res.status_code == 200
    data = res.json()
    assert "count" in data
    assert "next" in data
    assert "previous" in data
    assert "results" in data
    assert len(data["results"]) == 1

    # Filter search (case-insensitive name)
    res = client.get("/api/products/?search=brake")
    assert res.status_code == 200
    skus = [r["sku"] for r in res.json()["results"]]
    assert "TEST-001" in skus
    assert "TEST-002" not in skus

    # Filter category
    res = client.get("/api/products/?category=Brakes")
    assert res.status_code == 200
    skus = [r["sku"] for r in res.json()["results"]]
    assert "TEST-001" in skus
    assert "TEST-002" not in skus

    # Filter vehicle substring
    res = client.get("/api/products/?vehicle=duke")
    assert res.status_code == 200
    skus = [r["sku"] for r in res.json()["results"]]
    assert "TEST-001" in skus


@pytest.mark.django_db
def test_product_create_and_duplicate():
    client = APIClient()
    payload = {
        "sku": "NEW-101",
        "name": "New Handle Grip",
        "category": "Controls & Grips",
        "brand": "Progrip",
        "vehicle_fitment": "Universal",
        "price": "499.00",
        "description": "Premium grip",
    }
    res = client.post("/api/products/", payload, format="json")
    assert res.status_code == 201
    data = res.json()
    assert data["sku"] == "NEW-101"
    assert data["price"] == "499.00"
    assert data["stock"] == 0

    # Duplicate SKU returns 409 DUPLICATE
    res_dup = client.post("/api/products/", payload, format="json")
    assert res_dup.status_code == 409
    err = res_dup.json()["error"]
    assert err["code"] == "DUPLICATE"


@pytest.mark.django_db
def test_product_invalid_price():
    client = APIClient()
    payload = {
        "sku": "BAD-PRICE",
        "name": "Bad Product",
        "category": "Brakes",
        "brand": "Endurance",
        "vehicle_fitment": "Universal",
        "price": "-50.00",
    }
    res = client.post("/api/products/", payload, format="json")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"

    # More than 2 decimal places
    payload["price"] = "12.345"
    res2 = client.post("/api/products/", payload, format="json")
    assert res2.status_code == 400
    assert res2.json()["error"]["code"] == "VALIDATION_ERROR"
