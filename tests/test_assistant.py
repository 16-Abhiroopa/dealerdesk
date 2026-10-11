import os
import pytest
from rest_framework.test import APIClient
from dealers.models import Dealer
from products.models import Product, Inventory
from assistant.models import ChatSession, ChatMessage


@pytest.fixture(autouse=True)
def force_mock_llm():
    """Ensure tests run deterministically with MockLLMAdapter."""
    os.environ["USE_MOCK_LLM"] = "1"
    yield
    os.environ.pop("USE_MOCK_LLM", None)


@pytest.mark.django_db
def test_assistant_validation_errors():
    client = APIClient()
    dealer = Dealer.objects.create(dealer_code="DLR-AST-1", name="Assistant Test Dealer")

    # Missing message
    res1 = client.post("/api/assistant/chat/", {"session_id": "s1", "dealer_id": dealer.id, "message": ""}, format="json")
    assert res1.status_code == 400
    assert res1.json()["error"]["code"] == "VALIDATION_ERROR"

    # Unknown dealer
    res2 = client.post("/api/assistant/chat/", {"session_id": "s1", "dealer_id": 99999, "message": "hello"}, format="json")
    assert res2.status_code == 400
    assert res2.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
def test_assistant_off_topic_declined():
    client = APIClient()
    dealer = Dealer.objects.create(dealer_code="DLR-AST-2", name="Dealer 2")

    res = client.post(
        "/api/assistant/chat/",
        {"session_id": "s-offtopic", "dealer_id": dealer.id, "message": "What is the weather today in Bengaluru?"},
        format="json",
    )
    assert res.status_code == 200
    data = res.json()
    assert "automotive parts" in data["reply"] or "catalogue" in data["reply"]
    assert data["tool_calls"] == []
    assert data["cited_skus"] == []


@pytest.mark.django_db
def test_assistant_ambiguous_request():
    client = APIClient()
    dealer = Dealer.objects.create(dealer_code="DLR-AST-3", name="Dealer 3")

    # Ambiguous "brake pads" without vehicle
    res = client.post(
        "/api/assistant/chat/",
        {"session_id": "s-ambig", "dealer_id": dealer.id, "message": "Do you have brake pads?"},
        format="json",
    )
    assert res.status_code == 200
    data = res.json()
    # Must ask clarifying question about vehicle
    assert "vehicle" in data["reply"].lower() or "model" in data["reply"].lower()
    assert data["actions"] == []


@pytest.mark.django_db
def test_assistant_search_and_grounded_numbers():
    client = APIClient()
    dealer = Dealer.objects.create(dealer_code="DLR-AST-4", name="Dealer 4")
    p = Product.objects.create(
        sku="BRK-1044",
        name="Brake Pad Set - Bajaj Pulsar 150",
        category="Brakes",
        brand="Endurance",
        vehicle_fitment="Bajaj Pulsar 150",
        price="1459.50",
    )
    Inventory.objects.create(product=p, quantity=136)

    res = client.post(
        "/api/assistant/chat/",
        {"session_id": "s-search", "dealer_id": dealer.id, "message": "Do you have brake pads for a Pulsar 150?"},
        format="json",
    )
    assert res.status_code == 200
    data = res.json()
    assert "BRK-1044" in data["cited_skus"]
    assert any(tc["name"] == "search_parts" for tc in data["tool_calls"])
    assert "1459.50" in data["reply"]
    assert "136" in data["reply"]


@pytest.mark.django_db
def test_assistant_multi_turn_followup_and_draft_creation():
    client = APIClient()
    dealer = Dealer.objects.create(dealer_code="DLR-AST-5", name="Dealer 5")
    p = Product.objects.create(
        sku="BRK-1044",
        name="Brake Pad Set - Bajaj Pulsar 150",
        category="Brakes",
        brand="Endurance",
        vehicle_fitment="Bajaj Pulsar 150",
        price="1459.50",
    )
    Inventory.objects.create(product=p, quantity=50)

    session_id = "s-order-flow"

    # Turn 1: Search
    res1 = client.post(
        "/api/assistant/chat/",
        {"session_id": session_id, "dealer_id": dealer.id, "message": "Looking for brake pads for Pulsar 150"},
        format="json",
    )
    assert res1.status_code == 200

    # Turn 2: Follow up: "Put 10 aside for me" -> should resolve previous SKU and create DRAFT order
    res2 = client.post(
        "/api/assistant/chat/",
        {"session_id": session_id, "dealer_id": dealer.id, "message": "Put 10 aside for me"},
        format="json",
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert any(tc["name"] == "create_draft_order" for tc in data2["tool_calls"])
    assert len(data2["actions"]) == 1
    action = data2["actions"][0]
    assert action["type"] == "draft_order_created"
    assert "ORD-" in action["order_number"]


@pytest.mark.django_db
def test_assistant_session_isolation():
    client = APIClient()
    d1 = Dealer.objects.create(dealer_code="DLR-S1", name="Dealer 1")
    d2 = Dealer.objects.create(dealer_code="DLR-S2", name="Dealer 2")
    p = Product.objects.create(
        sku="FIL-9999",
        name="Special Air Filter",
        category="Filters",
        brand="Mahle",
        vehicle_fitment="Universal",
        price="200.00",
    )
    Inventory.objects.create(product=p, quantity=20)

    # Session A discusses FIL-9999
    client.post("/api/assistant/chat/", {"session_id": "sess-A", "dealer_id": d1.id, "message": "Check FIL-9999"}, format="json")

    # Session B says "Put 10 aside for me" without context -> must NOT inherit session A's SKU!
    resB = client.post("/api/assistant/chat/", {"session_id": "sess-B", "dealer_id": d2.id, "message": "Put 10 aside for me"}, format="json")
    assert resB.status_code == 200
    # Must ask which product rather than creating draft for FIL-9999
    assert resB.json()["actions"] == []
    assert "which" in resB.json()["reply"].lower() or "product" in resB.json()["reply"].lower()
