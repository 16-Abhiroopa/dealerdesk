"""Hybrid retrieval for DealerDesk catalogue.

Combines:
- Vehicle-fitment normalisation and substring matching (e.g. "Duke 390" -> "KTM Duke 390")
- Category intent matching
- In-memory BM25 / token-overlap scoring on trusted metadata:
  searchable_text = f"{name} {brand} {category} {vehicle_fitment}"
  (raw supplier descriptions are strictly excluded to prevent prompt injections)
- Live database hydration for current stock and catalogue price.
"""
import re
from typing import List, Dict, Optional, Tuple
from core.utils import format_money
from products.models import Product

CANONICAL_VEHICLES = [
    "Bajaj Dominar 400",
    "Bajaj Pulsar 150",
    "Bajaj Pulsar NS200",
    "Hero Splendor Plus",
    "Hero Xtreme 160R",
    "Honda Hornet 2.0",
    "Honda Shine 125",
    "Hyundai Creta",
    "Hyundai i20",
    "KTM Duke 200",
    "KTM Duke 390",
    "Mahindra Thar",
    "Maruti Baleno",
    "Maruti Swift",
    "Royal Enfield Classic 350",
    "Royal Enfield Himalayan 450",
    "Royal Enfield Hunter 350",
    "Suzuki Gixxer SF",
    "TVS Apache RTR 160",
    "TVS Apache RTR 200",
    "Tata Nexon",
    "Universal",
    "Yamaha FZ-S",
    "Yamaha MT-15",
    "Yamaha R15 V4",
]

VEHICLE_SYNONYMS = {
    "duke 390": "KTM Duke 390",
    "390": "KTM Duke 390",
    "duke 200": "KTM Duke 200",
    "pulsar 150": "Bajaj Pulsar 150",
    "pulsar ns200": "Bajaj Pulsar NS200",
    "ns200": "Bajaj Pulsar NS200",
    "pulsar": "Bajaj Pulsar 150",
    "dominar 400": "Bajaj Dominar 400",
    "dominar": "Bajaj Dominar 400",
    "splendor plus": "Hero Splendor Plus",
    "splendor": "Hero Splendor Plus",
    "xtreme 160r": "Hero Xtreme 160R",
    "xtreme": "Hero Xtreme 160R",
    "hornet 2.0": "Honda Hornet 2.0",
    "hornet": "Honda Hornet 2.0",
    "shine 125": "Honda Shine 125",
    "shine": "Honda Shine 125",
    "classic 350": "Royal Enfield Classic 350",
    "himalayan 450": "Royal Enfield Himalayan 450",
    "himalayan": "Royal Enfield Himalayan 450",
    "hunter 350": "Royal Enfield Hunter 350",
    "gixxer sf": "Suzuki Gixxer SF",
    "gixxer": "Suzuki Gixxer SF",
    "apache rtr 160": "TVS Apache RTR 160",
    "apache 160": "TVS Apache RTR 160",
    "apache rtr 200": "TVS Apache RTR 200",
    "apache 200": "TVS Apache RTR 200",
    "apache": "TVS Apache RTR 200",
    "fz-s": "Yamaha FZ-S",
    "fzs": "Yamaha FZ-S",
    "mt-15": "Yamaha MT-15",
    "mt15": "Yamaha MT-15",
    "r15 v4": "Yamaha R15 V4",
    "r15": "Yamaha R15 V4",
    "thar": "Mahindra Thar",
    "creta": "Hyundai Creta",
    "i20": "Hyundai i20",
    "baleno": "Maruti Baleno",
    "swift": "Maruti Swift",
    "nexon": "Tata Nexon",
}

CATEGORY_SYNONYMS = {
    "brake": "Brakes",
    "pad": "Brakes",
    "rotor": "Brakes",
    "disc": "Brakes",
    "shoe": "Brakes",
    "oil": "Engine & Oils",
    "coolant": "Engine & Oils",
    "filter": "Filters",
    "chain": "Drivetrain",
    "sprocket": "Drivetrain",
    "spark": "Lighting & Electrical",
    "plug": "Lighting & Electrical",
    "indicator": "Lighting & Electrical",
    "battery": "Lighting & Electrical",
    "grip": "Controls & Grips",
    "lever": "Controls & Grips",
    "peg": "Controls & Grips",
    "mirror": "Body & Styling",
    "crash": "Body & Styling",
    "guard": "Body & Styling",
    "pad": "Body & Styling",
    "cover": "Universal Accessories",
    "tyre": "Tyres & Tubes",
    "tire": "Tyres & Tubes",
    "tube": "Tyres & Tubes",
}


def normalize_vehicle(text: Optional[str]) -> Optional[str]:
    """Extract or normalize vehicle name from text."""
    if not text:
        return None
    lower = text.lower().strip()
    for syn, canonical in sorted(VEHICLE_SYNONYMS.items(), key=lambda x: -len(x[0])):
        if syn in lower:
            return canonical
    for can in CANONICAL_VEHICLES:
        if can.lower() in lower:
            return can
    return None


def normalize_category(text: Optional[str]) -> Optional[str]:
    """Extract or normalize category from text."""
    if not text:
        return None
    lower = text.lower().strip()
    for syn, cat in CATEGORY_SYNONYMS.items():
        if syn in lower:
            return cat
    return None


def tokenize(text: str) -> List[str]:
    """Simple alphanumeric tokenization."""
    return re.findall(r"\w+", text.lower())


def search_catalogue(
    query: str,
    vehicle: Optional[str] = None,
    category: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict]:
    """Retrieve top-k relevant products using hybrid scoring, hydrated with live stock and price."""
    # 1. Normalize vehicle and category intents
    target_vehicle = normalize_vehicle(vehicle) or normalize_vehicle(query)
    target_category = normalize_category(category) or normalize_category(query)

    query_tokens = set(tokenize(query))
    if vehicle:
        query_tokens.update(tokenize(vehicle))
    if category:
        query_tokens.update(tokenize(category))

    # Pre-filter query
    qs = Product.objects.select_related("inventory").all()

    # Exact SKU lookup shortcut
    sku_match = re.search(r"\b[A-Z]{3}-\d{4}\b", query.upper())
    if sku_match:
        sku_target = sku_match.group(0)
        direct_p = qs.filter(sku=sku_target).first()
        if direct_p:
            return [{
                "sku": direct_p.sku,
                "name": direct_p.name,
                "category": direct_p.category,
                "brand": direct_p.brand,
                "vehicle_fitment": direct_p.vehicle_fitment,
                "price": format_money(direct_p.price),
                "stock": direct_p.stock,
            }]

    scored_products: List[Tuple[float, Product]] = []

    for p in qs:
        # Searchable text strictly uses trusted attributes (NEVER raw description)
        searchable_text = f"{p.name} {p.brand} {p.category} {p.vehicle_fitment}"
        doc_tokens = set(tokenize(searchable_text))

        # Lexical score (Jaccard / token overlap)
        overlap = query_tokens.intersection(doc_tokens)
        if not overlap and not (target_vehicle and (p.vehicle_fitment == target_vehicle or p.vehicle_fitment == "Universal")):
            continue

        score = float(len(overlap))

        # Vehicle matching boost
        if target_vehicle:
            if p.vehicle_fitment == target_vehicle:
                score += 10.0
            elif p.vehicle_fitment == "Universal":
                score += 3.0
            else:
                # Penalize mismatch if a specific vehicle was requested
                score -= 8.0

        # Category matching boost
        if target_category and p.category.lower() == target_category.lower():
            score += 5.0

        if score > 0:
            scored_products.append((score, p))

    # Sort descending by score, tiebreak by stock
    scored_products.sort(key=lambda item: (item[0], item[1].stock), reverse=True)

    results = []
    for _, prod in scored_products[:top_k]:
        results.append({
            "sku": prod.sku,
            "name": prod.name,
            "category": prod.category,
            "brand": prod.brand,
            "vehicle_fitment": prod.vehicle_fitment,
            "price": format_money(prod.price),
            "stock": prod.stock,
        })

    return results
