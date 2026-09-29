"""Order workflow: create an order from a cart, then check out."""
from shop.models import Order
from shop.pricing import calculate_total, summarize_total
from shop.notify import send_confirmation
from shop.utils import log


def create_order(customer, cart):
    """Create an order for a valid customer. cart is a list of (product, qty)."""
    if not customer.is_valid():
        raise ValueError("Invalid customer")
    order = Order(customer)
    for product, qty in cart:
        order.add_item(product, qty)
    log(f"Order created for {customer.name}")
    return order


def checkout(order, discount_code=None):
    """Calculate the total, notify the customer and return a formatted total."""
    total = calculate_total(order.items(), discount_code)
    send_confirmation(order.customer, total)
    return summarize_total(total)
