"""Supplier Catalogue Sync Service implementing Section 8 of API_CONTRACT.md."""
import time
import re
import logging
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, List, Optional
import requests
from django.conf import settings
from django.db import transaction

from core.exceptions import SupplierUnavailableAppError
from products.models import Product, Inventory

logger = logging.getLogger(__name__)

PRICE_REGEX = re.compile(r"^\d+(\.\d{1,2})?$")


def is_valid_price(price_val: Any) -> bool:
    """Validate that price is a positive amount with at most 2 decimal places."""
    if price_val is None:
        return False
    price_str = str(price_val).strip()
    if not PRICE_REGEX.match(price_str):
        return False
    try:
        dec = Decimal(price_str)
        return dec > 0
    except (InvalidOperation, ValueError):
        return False


def run_supplier_sync() -> Dict[str, Any]:
    """Execute full supplier catalog synchronization.

    Returns:
        dict with keys: created, updated, unchanged, rejected, pages_fetched, requests_made
    Raises:
        SupplierUnavailableAppError on permanent failure or missing config
    """
    base_url = (getattr(settings, "SUPPLIER_API_URL", "") or "").rstrip("/")
    api_key = getattr(settings, "SUPPLIER_API_KEY", "") or ""

    if not base_url or not api_key:
        logger.error("SUPPLIER_API_URL or SUPPLIER_API_KEY is not configured.")
        raise SupplierUnavailableAppError("Supplier API configuration missing.")

    endpoint = f"{base_url}/v1/products"
    headers = {"X-Api-Key": api_key}

    cursor = None
    all_raw_items: List[Dict[str, Any]] = []
    pages_fetched = 0
    requests_made = 0

    max_attempts = 5

    # 1. Paginated Fetch with Resilient Retries
    while True:
        params = {"limit": 20}
        if cursor:
            params["cursor"] = cursor

        success = False
        response_data = None

        for attempt in range(max_attempts):
            requests_made += 1
            try:
                resp = requests.get(endpoint, params=params, headers=headers, timeout=20)
                if resp.status_code == 200:
                    pages_fetched += 1
                    response_data = resp.json()
                    success = True
                    break
                elif resp.status_code == 401 or resp.status_code == 403:
                    logger.warning("Supplier API key rejected with status %d", resp.status_code)
                    raise SupplierUnavailableAppError("Supplier API key rejected.")
                elif resp.status_code == 429:
                    retry_after_hdr = resp.headers.get("Retry-After")
                    try:
                        wait_seconds = int(retry_after_hdr) if retry_after_hdr else 1
                    except ValueError:
                        wait_seconds = 1
                    time.sleep(wait_seconds)
                elif resp.status_code >= 500:
                    backoff = min(4.0, 0.25 * (2**attempt))
                    time.sleep(backoff)
                else:
                    # Client errors (400, 404, etc.)
                    logger.warning("Supplier API unexpected client error %d", resp.status_code)
                    raise SupplierUnavailableAppError(f"Supplier API returned status {resp.status_code}")

            except requests.RequestException as exc:
                if attempt == max_attempts - 1:
                    logger.exception("Supplier API network failure on attempt %d: %s", attempt + 1, exc)
                    raise SupplierUnavailableAppError("Failed to reach supplier API after multiple attempts.")
                backoff = min(4.0, 0.25 * (2**attempt))
                time.sleep(backoff)

        if not success or response_data is None:
            raise SupplierUnavailableAppError("Supplier sync could not fetch full feed.")

        items = response_data.get("items", [])
        all_raw_items.extend(items)

        next_cursor = response_data.get("next_cursor")
        if not next_cursor:
            # Reached last page
            break
        cursor = next_cursor

    # 2. Filter Invalid Items & Track Rejections
    valid_items: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    for item in all_raw_items:
        supplier_sku = item.get("supplier_sku")
        sku = item.get("sku")
        price = item.get("price")

        if not sku or not isinstance(sku, str) or not sku.strip():
            rejected.append({
                "supplier_sku": supplier_sku,
                "reason": "missing or empty sku",
            })
            continue

        if not is_valid_price(price):
            rejected.append({
                "supplier_sku": supplier_sku,
                "reason": "invalid price",
            })
            continue

        valid_items.append(item)

    # 3. Deduplicate by SKU Keeping Latest updated_at
    latest_by_sku: Dict[str, Dict[str, Any]] = {}
    for item in valid_items:
        sku = item["sku"].strip()
        item_updated = item.get("updated_at") or ""
        if sku not in latest_by_sku:
            latest_by_sku[sku] = item
        else:
            prev_updated = latest_by_sku[sku].get("updated_at") or ""
            if item_updated > prev_updated:
                latest_by_sku[sku] = item

    # 4. Atomic Database Update (All-or-Nothing)
    created_count = 0
    updated_count = 0
    unchanged_count = 0

    with transaction.atomic():
        # Pre-fetch existing products by SKU
        existing_products = {p.sku: p for p in Product.objects.filter(sku__in=latest_by_sku.keys())}

        for sku, item in latest_by_sku.items():
            name = (item.get("name") or "").strip()
            category = (item.get("category") or "").strip()
            brand = (item.get("brand") or "").strip()
            vehicle_fitment = (item.get("vehicle_fitment") or "").strip()
            description = (item.get("description") or "").strip()
            price_dec = Decimal(str(item["price"])).quantize(Decimal("0.01"))

            if sku not in existing_products:
                new_prod = Product.objects.create(
                    sku=sku,
                    name=name,
                    category=category,
                    brand=brand,
                    vehicle_fitment=vehicle_fitment,
                    description=description,
                    price=price_dec,
                )
                Inventory.objects.create(product=new_prod, quantity=0)
                created_count += 1
            else:
                p = existing_products[sku]
                curr_price = Decimal(str(p.price)).quantize(Decimal("0.01"))
                has_diff = (
                    p.name != name
                    or p.category != category
                    or p.brand != brand
                    or p.vehicle_fitment != vehicle_fitment
                    or p.description != description
                    or curr_price != price_dec
                )

                if has_diff:
                    p.name = name
                    p.category = category
                    p.brand = brand
                    p.vehicle_fitment = vehicle_fitment
                    p.description = description
                    p.price = price_dec
                    p.save()
                    updated_count += 1
                else:
                    unchanged_count += 1

    return {
        "created": created_count,
        "updated": updated_count,
        "unchanged": unchanged_count,
        "rejected": rejected,
        "pages_fetched": pages_fetched,
        "requests_made": requests_made,
    }
