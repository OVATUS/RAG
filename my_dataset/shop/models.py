"""Data models: Product, Customer and Order."""
from shop.utils import validate_email


class Product:
    def __init__(self, name, price, stock):
        self.name = name
        self.price = price
        self.stock = stock

    def is_available(self, qty=1):
        """A product is available when there is enough stock."""
        return self.stock >= qty

    def reduce_stock(self, qty):
        """Reduce stock after a purchase. Raises ValueError if stock is not enough."""
        if not self.is_available(qty):
            raise ValueError(f"Not enough stock for {self.name}")
        self.stock -= qty


class Customer:
    def __init__(self, name, email):
        self.name = name
        self.email = email

    def is_valid(self):
        """A customer is valid when the name is not empty and the email is valid."""
        return bool(self.name) and validate_email(self.email)


class Order:
    def __init__(self, customer):
        self.customer = customer
        self.lines = []  # list of (product, qty)

    def add_item(self, product, qty=1):
        """Add a product to the order and reduce its stock."""
        product.reduce_stock(qty)
        self.lines.append((product, qty))

    def items(self):
        """Return (price, qty) pairs used for price calculation."""
        return [(p.price, q) for p, q in self.lines]
