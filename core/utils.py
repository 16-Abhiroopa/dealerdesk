"""Utility functions for money formatting, decimal rounding, and timestamp formatting."""
from decimal import Decimal, ROUND_HALF_UP
import re

MONEY_REGEX = re.compile(r"^\d+(\.\d{1,2})?$")


def format_money(val) -> str:
    """Format any number/decimal into exact 2-decimal string like '1459.50'."""
    if val is None:
        return "0.00"
    if not isinstance(val, Decimal):
        val = Decimal(str(val))
    return str(val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def round_half_up(val: Decimal) -> Decimal:
    """Round a Decimal using ROUND_HALF_UP to the paisa (2 decimal places)."""
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def is_valid_price(price_val) -> bool:
    """Validate price: must be positive Decimal with at most 2 decimal places."""
    try:
        if isinstance(price_val, str):
            if not MONEY_REGEX.match(price_val):
                return False
            d = Decimal(price_val)
        elif isinstance(price_val, (int, float, Decimal)):
            d = Decimal(str(price_val))
            # check decimal places
            t = d.as_tuple()
            if t.exponent < -2:
                return False
        else:
            return False
        return d > Decimal("0.00")
    except Exception:
        return False
