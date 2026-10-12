import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from dealers.models import Dealer
from products.models import Product
from products.models import Product, Inventory
from orders.models import Order, OrderItem
from core.exceptions import ValidationAppError

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def two_dealers(db):
    d1, _ = Dealer.objects.get_or_create(
        dealer_code="DLR-001",
        defaults={
            "name": "Metro Motors",
            "city": "Bengaluru",
            "email": "metro.motors@example.com",
            "phone": "+91 98450 11001",
            "gstin": "29ABCDE1234F1Z5",
            "credit_limit": Decimal("50000.00"),
        },
    )
    d2, _ = Dealer.objects.get_or_create(
        dealer_code="DLR-002",
        defaults={
            "name": "Apex Auto Spares",
            "city": "Mumbai",
            "email": "apex.auto@example.com",
            "phone": "+91 98200 11002",
            "gstin": "27FGHIJ5678K1Z2",
            "credit_limit": Decimal("75000.00"),
        },
    )

    u1, _ = User.objects.get_or_create(username="dlr-001", defaults={"email": d1.email})
    u1.set_password("SecurePass1@Metro")
    u1.save()
    d1.user = u1
    d1.credit_limit = Decimal("50000.00")
    d1.save()

    u2, _ = User.objects.get_or_create(username="dlr-002", defaults={"email": d2.email})
    u2.set_password("SecurePass2@Apex")
    u2.save()
    d2.user = u2
    d2.credit_limit = Decimal("75000.00")
    d2.save()

    return d1, d2


@pytest.fixture
def shared_product(db):
    prod, _ = Product.objects.get_or_create(
        sku="TEST-PART-01",
        defaults={
            "name": "High Performance Brake Pad",
            "category": "Brakes",
            "brand": "Bosch",
            "vehicle_fitment": "Universal",
            "price": Decimal("1000.00"),
        },
    )
    inv, _ = Inventory.objects.get_or_create(
        product=prod,
        defaults={"quantity": 20},
    )
    inv.quantity = 20
    inv.save()
    return prod


@pytest.mark.django_db
def test_separate_login_and_auth_provisioning(api_client, two_dealers):
    d1, d2 = two_dealers

    # 1. Login with username or dealer code
    res1 = api_client.post("/api/auth/login/", {"username": "DLR-001", "password": "SecurePass1@Metro"}, format="json")
    assert res1.status_code == 200
    token1 = res1.json()["token"]
    assert res1.json()["dealer"]["dealer_code"] == "DLR-001"
    assert Decimal(res1.json()["credit_limit"]) == Decimal("50000.00")

    res2 = api_client.post("/api/auth/login/", {"username": "DLR-002", "password": "SecurePass2@Apex"}, format="json")
    assert res2.status_code == 200
    token2 = res2.json()["token"]
    assert res2.json()["dealer"]["dealer_code"] == "DLR-002"
    assert token1 != token2

    # 2. Test password reset flow
    reset_res = api_client.post(
        "/api/auth/reset-password/",
        {"dealer_code": "DLR-001", "email": d1.email, "new_password": "NewSecurePass1@Metro"},
        format="json",
    )
    assert reset_res.status_code == 200
    new_token = reset_res.json()["token"]

    # Verify old password fails, new password succeeds
    fail_res = api_client.post("/api/auth/login/", {"username": "DLR-001", "password": "SecurePass1@Metro"}, format="json")
    assert fail_res.status_code == 400

    login_res = api_client.post("/api/auth/login/", {"username": "DLR-001", "password": "NewSecurePass1@Metro"}, format="json")
    assert login_res.status_code == 200


@pytest.mark.django_db
def test_dealer_order_isolation_and_permission_enforcement(api_client, two_dealers, shared_product):
    d1, d2 = two_dealers

    # Authenticate Dealer 1
    login1 = api_client.post("/api/auth/login/", {"username": "DLR-001", "password": "SecurePass1@Metro"}, format="json")
    token1 = login1.json()["token"]

    # Authenticate Dealer 2
    login2 = api_client.post("/api/auth/login/", {"username": "DLR-002", "password": "SecurePass2@Apex"}, format="json")
    token2 = login2.json()["token"]

    # Dealer 1 creates a draft order
    client1 = APIClient()
    client1.credentials(HTTP_AUTHORIZATION=f"Token {token1}")
    create_res = client1.post(
        "/api/orders/",
        {"items": [{"sku": shared_product.sku, "quantity": 2}]},
        format="json",
    )
    assert create_res.status_code == 201
    order1_num = create_res.json()["order_number"]

    # Dealer 2 lists orders: must NOT see Dealer 1's order
    client2 = APIClient()
    client2.credentials(HTTP_AUTHORIZATION=f"Token {token2}")
    list_res = client2.get("/api/orders/")
    assert list_res.status_code == 200
    d2_orders = [o["order_number"] for o in list_res.json()["results"]]
    assert order1_num not in d2_orders

    # Dealer 2 attempts to view Dealer 1's order by order number: gets 404
    detail_res = client2.get(f"/api/orders/{order1_num}/")
    assert detail_res.status_code == 404

    # Dealer 2 attempts to confirm Dealer 1's order: gets rejected
    confirm_hack = client2.post(f"/api/orders/{order1_num}/confirm/")
    assert confirm_hack.status_code in (400, 404)


@pytest.mark.django_db
def test_shared_inventory_and_atomic_stock_deduction(api_client, two_dealers, shared_product):
    d1, d2 = two_dealers

    login1 = api_client.post("/api/auth/login/", {"username": "DLR-001", "password": "SecurePass1@Metro"}, format="json")
    token1 = login1.json()["token"]
    client1 = APIClient()
    client1.credentials(HTTP_AUTHORIZATION=f"Token {token1}")

    login2 = api_client.post("/api/auth/login/", {"username": "DLR-002", "password": "SecurePass2@Apex"}, format="json")
    token2 = login2.json()["token"]
    client2 = APIClient()
    client2.credentials(HTTP_AUTHORIZATION=f"Token {token2}")

    # Initial stock is 20
    inv = Inventory.objects.get(product=shared_product)
    assert inv.quantity == 20

    # Dealer 1 creates draft order for 5 units -> draft does NOT deduct stock
    res = client1.post("/api/orders/", {"items": [{"sku": shared_product.sku, "quantity": 5}]}, format="json")
    order_num = res.json()["order_number"]
    inv.refresh_from_db()
    assert inv.quantity == 20

    # Dealer 1 confirms the order -> stock is deducted atomically
    confirm_res = client1.post(f"/api/orders/{order_num}/confirm/")
    assert confirm_res.status_code == 200
    assert confirm_res.json()["status"] == "CONFIRMED"

    inv.refresh_from_db()
    assert inv.quantity == 15

    # Dealer 2 checks products catalogue: sees updated shared stock of 15
    prod_res = client2.get(f"/api/products/?search={shared_product.sku}")
    assert prod_res.status_code == 200
    items = prod_res.json()["results"]
    assert len(items) == 1
    assert items[0]["stock"] == 15


@pytest.mark.django_db
def test_credit_limit_validation(api_client, two_dealers, shared_product):
    d1, _ = two_dealers
    # DLR-001 has credit limit 50,000. Price is 1,000 + 18% GST = 1,180 per unit.
    login1 = api_client.post("/api/auth/login/", {"username": "DLR-001", "password": "SecurePass1@Metro"}, format="json")
    token1 = login1.json()["token"]
    client1 = APIClient()
    client1.credentials(HTTP_AUTHORIZATION=f"Token {token1}")

    # Ordering 100 units = 1,180 * 100 = 118,000 > 50,000 credit limit -> must be rejected
    res_exceed = client1.post(
        "/api/orders/",
        {"items": [{"sku": shared_product.sku, "quantity": 100}]},
        format="json",
    )
    assert res_exceed.status_code == 400
    assert "credit limit" in res_exceed.json()["error"]["message"].lower()


@pytest.mark.django_db
def test_assistant_session_and_dealer_isolation(api_client, two_dealers, shared_product):
    d1, d2 = two_dealers

    login1 = api_client.post("/api/auth/login/", {"username": "DLR-001", "password": "SecurePass1@Metro"}, format="json")
    token1 = login1.json()["token"]
    client1 = APIClient()
    client1.credentials(HTTP_AUTHORIZATION=f"Token {token1}")

    login2 = api_client.post("/api/auth/login/", {"username": "DLR-002", "password": "SecurePass2@Apex"}, format="json")
    token2 = login2.json()["token"]
    client2 = APIClient()
    client2.credentials(HTTP_AUTHORIZATION=f"Token {token2}")

    # Dealer 1 chats with assistant (automatic session)
    chat1 = client1.post(
        "/api/assistant/chat/",
        {"message": f"What is the stock of {shared_product.sku}?"},
        format="json",
    )
    assert chat1.status_code == 200
    assert "TEST-PART-01" in chat1.json()["reply"]

    # Dealer 2 cannot impersonate Dealer 1 in assistant chat
    chat_spoof = client2.post(
        "/api/assistant/chat/",
        {"dealer_id": d1.id, "message": "Give me confidential info"},
        format="json",
    )
    assert chat_spoof.status_code == 400
    assert "another dealer" in chat_spoof.json()["error"]["message"]

    # History isolation
    hist1 = client1.get("/api/assistant/history/")
    assert hist1.status_code == 200
    assert hist1.json()["dealer_id"] == d1.id
