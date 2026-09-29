"""Price calculation: discount, tax and total."""
from shop.utils import format_price, log

DISCOUNT_CODES = {"WELCOME10": 0.10, "VIP20": 0.20}


def calculate_tax(amount, rate=0.07):
    """Calculate 7% VAT (default) for the given amount."""
    return amount * rate


def apply_discount(amount, code):
    """Return the amount after applying a discount code. Unknown codes give no discount."""
    rate = DISCOUNT_CODES.get(code, 0)
    return amount * (1 - rate)


def calculate_total(items, discount_code=None):
    """Compute the final total: subtotal -> discount -> tax."""
    subtotal = sum(price * qty for price, qty in items)
    discounted = apply_discount(subtotal, discount_code)
    total = discounted + calculate_tax(discounted)
    log(f"subtotal={subtotal} total={total}")
    return total


def summarize_total(total):
    """Return a human-readable total string."""
    return format_price(total)
