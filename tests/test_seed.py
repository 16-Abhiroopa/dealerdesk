import pytest
from django.core.management import call_command
from products.models import Product, Inventory
from dealers.models import Dealer


@pytest.mark.django_db
def test_seed_data_idempotent():
    call_command("seed_data")
    count_p1 = Product.objects.count()
    count_inv1 = Inventory.objects.count()
    count_d1 = Dealer.objects.count()

    assert count_p1 == 600
    assert count_inv1 == 600
    assert count_d1 == 25

    # Run seed_data a second time
    call_command("seed_data")
    count_p2 = Product.objects.count()
    count_inv2 = Inventory.objects.count()
    count_d2 = Dealer.objects.count()

    assert count_p2 == 600
    assert count_inv2 == 600
    assert count_d2 == 25
