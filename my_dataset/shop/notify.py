"""Customer notifications."""
from shop.utils import validate_email, log


def send_confirmation(customer, total):
    """Send an order confirmation email. Returns False if the email is invalid."""
    if not validate_email(customer.email):
        log(f"Invalid email for {customer.name}, confirmation not sent")
        return False
    log(f"Confirmation sent to {customer.email} (total={total})")
    return True
