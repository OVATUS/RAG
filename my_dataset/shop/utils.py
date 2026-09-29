"""Small helper functions shared across the shop package."""


def validate_email(email):
    """Return True if the email looks valid (has '@' and a dot in the domain)."""
    if "@" not in email:
        return False
    return "." in email.split("@")[-1]


def format_price(amount):
    """Format a number as a Thai baht price string, e.g. 1,234.50 THB."""
    return f"{amount:,.2f} THB"


def log(message):
    """Print a log line with a [LOG] prefix."""
    print(f"[LOG] {message}")
