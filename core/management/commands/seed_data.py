import csv
from decimal import Decimal
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from products.models import Product, Inventory
from dealers.models import Dealer


class Command(BaseCommand):
    help = "Idempotently load data from data/ into the PostgreSQL database."

    def handle(self, *args, **options):
        data_dir: Path = settings.DATA_DIR
        catalogue_path = data_dir / "catalogue.csv"
        dealers_path = data_dir / "dealers.csv"

        if not catalogue_path.exists():
            self.stdout.write(self.style.ERROR(f"Catalogue file not found: {catalogue_path}"))
            return

        if not dealers_path.exists():
            self.stdout.write(self.style.ERROR(f"Dealers file not found: {dealers_path}"))
            return

        with transaction.atomic():
            # 1. Seed Products and Starting Inventory
            products_count = 0
            with open(catalogue_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    sku = row["sku"].strip()
                    name = row["name"].strip()
                    category = row["category"].strip()
                    brand = row["brand"].strip()
                    vehicle_fitment = row["vehicle_fitment"].strip()
                    price = Decimal(row["price"].strip())
                    description = row.get("description", "")
                    stock = int(row.get("stock", 0))

                    product, _ = Product.objects.update_or_create(
                        sku=sku,
                        defaults={
                            "name": name,
                            "category": category,
                            "brand": brand,
                            "vehicle_fitment": vehicle_fitment,
                            "price": price,
                            "description": description,
                        },
                    )

                    Inventory.objects.update_or_create(
                        product=product,
                        defaults={"quantity": stock},
                    )
                    products_count += 1

            # 2. Seed Dealers
            dealers_count = 0
            with open(dealers_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    dealer_code = row["dealer_code"].strip()
                    name = row["name"].strip()
                    city = row.get("city", "").strip()
                    phone = row.get("phone", "").strip()
                    email = row.get("email", "").strip()
                    gstin = row.get("gstin", "").strip()
                    credit_limit = Decimal(row.get("credit_limit", "0.00").strip())

                    Dealer.objects.update_or_create(
                        dealer_code=dealer_code,
                        defaults={
                            "name": name,
                            "city": city,
                            "phone": phone,
                            "email": email,
                            "gstin": gstin,
                            "credit_limit": credit_limit,
                        },
                    )
                    dealers_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded {products_count} products (with inventory) and {dealers_count} dealers."
            )
        )
