from decimal import Decimal
import threading
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from dealers.models import Dealer
from products.models import Product, Inventory
from orders.models import Order, OrderItem


class OrderEngineTestCase(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        self.dealer = Dealer.objects.create(
            dealer_code="DLR-TST-1",
            name="Test Auto Spares",
            credit_limit=Decimal("50000.00"),
        )
        self.p1 = Product.objects.create(
            sku="ORD-P1",
            name="Disc Pad Front",
            category="Brakes",
            brand="Brembo",
            vehicle_fitment="Universal",
            price=Decimal("100.03"),
        )
        self.inv1 = Inventory.objects.create(product=self.p1, quantity=10)

        self.p2 = Product.objects.create(
            sku="ORD-P2",
            name="Air Filter",
            category="Filters",
            brand="Mahle",
            vehicle_fitment="Universal",
            price=Decimal("200.00"),
        )
        self.inv2 = Inventory.objects.create(product=self.p2, quantity=2)

    def test_gst_rounding_half_up_per_line(self):
        # 100.03 * 0.18 = 18.0054 -> ROUND_HALF_UP to 2 decimals is 18.01
        res = self.client.post(
            "/api/orders/",
            {"dealer_id": self.dealer.id, "items": [{"sku": "ORD-P1", "quantity": 1}]},
            format="json",
        )
        assert res.status_code == 201
        data = res.json()
        item = data["items"][0]
        assert item["line_subtotal"] == "100.03"
        assert item["line_tax"] == "18.01"
        assert item["line_total"] == "118.04"
        assert data["subtotal"] == "100.03"
        assert data["tax_total"] == "18.01"
        assert data["grand_total"] == "118.04"

    def test_confirm_all_or_nothing(self):
        # p1 has 10 stock, p2 has 2 stock. Requesting 2 of p1 and 5 of p2.
        res = self.client.post(
            "/api/orders/",
            {
                "dealer_id": self.dealer.id,
                "items": [
                    {"sku": "ORD-P1", "quantity": 2},
                    {"sku": "ORD-P2", "quantity": 5},
                ],
            },
            format="json",
        )
        assert res.status_code == 201
        order_num = res.json()["order_number"]

        # Confirm must fail because p2 has only 2 stock
        conf_res = self.client.post(f"/api/orders/{order_num}/confirm/")
        assert conf_res.status_code == 409
        err = conf_res.json()["error"]
        assert err["code"] == "INSUFFICIENT_STOCK"
        assert len(err["details"]) == 1
        assert err["details"][0] == {"sku": "ORD-P2", "requested": 5, "available": 2}

        # Verify stock was not deducted for either product (all-or-nothing)
        self.inv1.refresh_from_db()
        self.inv2.refresh_from_db()
        assert self.inv1.quantity == 10
        assert self.inv2.quantity == 2

    def test_price_lock_on_confirm(self):
        res = self.client.post(
            "/api/orders/",
            {"dealer_id": self.dealer.id, "items": [{"sku": "ORD-P1", "quantity": 1}]},
            format="json",
        )
        order_num = res.json()["order_number"]

        # Confirm order
        self.client.post(f"/api/orders/{order_num}/confirm/")

        # Change catalogue price of ORD-P1
        self.p1.price = Decimal("999.00")
        self.p1.save()

        # Confirmed order must retain locked price of 100.03
        get_res = self.client.get(f"/api/orders/{order_num}/")
        assert get_res.status_code == 200
        assert get_res.json()["items"][0]["unit_price"] == "100.03"

    def test_concurrent_confirms_no_overselling(self):
        # p2 has 2 units in stock
        res1 = self.client.post(
            "/api/orders/",
            {"dealer_id": self.dealer.id, "items": [{"sku": "ORD-P2", "quantity": 2}]},
            format="json",
        )
        ord1 = res1.json()["order_number"]

        res2 = self.client.post(
            "/api/orders/",
            {"dealer_id": self.dealer.id, "items": [{"sku": "ORD-P2", "quantity": 2}]},
            format="json",
        )
        ord2 = res2.json()["order_number"]

        results = []

        def confirm_worker(ord_num):
            c = APIClient()
            r = c.post(f"/api/orders/{ord_num}/confirm/")
            results.append((ord_num, r.status_code))

        t1 = threading.Thread(target=confirm_worker, args=(ord1,))
        t2 = threading.Thread(target=confirm_worker, args=(ord2,))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        statuses = [s for _, s in results]
        assert 200 in statuses
        assert 409 in statuses

        self.inv2.refresh_from_db()
        # Stock must be exactly 0, never negative!
        assert self.inv2.quantity == 0

    def test_cancel_restores_stock_exactly_once(self):
        # Create and confirm order with 2 units of ORD-P2
        res = self.client.post(
            "/api/orders/",
            {"dealer_id": self.dealer.id, "items": [{"sku": "ORD-P2", "quantity": 2}]},
            format="json",
        )
        order_num = res.json()["order_number"]
        self.client.post(f"/api/orders/{order_num}/confirm/")

        self.inv2.refresh_from_db()
        assert self.inv2.quantity == 0

        # Run concurrent cancels
        cancel_statuses = []

        def cancel_worker():
            c = APIClient()
            r = c.post(f"/api/orders/{order_num}/cancel/")
            cancel_statuses.append(r.status_code)

        t1 = threading.Thread(target=cancel_worker)
        t2 = threading.Thread(target=cancel_worker)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.inv2.refresh_from_db()
        # Stock must be restored to 2, never 4!
        assert self.inv2.quantity == 2
        # Exactly one cancel succeeded, other failed with 409 INVALID_TRANSITION
        assert cancel_statuses.count(200) == 1
        assert cancel_statuses.count(409) == 1

    def test_idempotency_key_behavior(self):
        body = {"dealer_id": self.dealer.id, "items": [{"sku": "ORD-P1", "quantity": 1}]}
        headers = {"HTTP_IDEMPOTENCY_KEY": "KEY-12345"}

        res1 = self.client.post("/api/orders/", body, format="json", **headers)
        assert res1.status_code == 201
        ord1 = res1.json()["order_number"]

        # Same key, identical body -> returns original order with 200
        res2 = self.client.post("/api/orders/", body, format="json", **headers)
        assert res2.status_code == 200
        assert res2.json()["order_number"] == ord1

        # Same key, different body -> 409 IDEMPOTENCY_CONFLICT
        different_body = {"dealer_id": self.dealer.id, "items": [{"sku": "ORD-P1", "quantity": 2}]}
        res3 = self.client.post("/api/orders/", different_body, format="json", **headers)
        assert res3.status_code == 409
        assert res3.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
