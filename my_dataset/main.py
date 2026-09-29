"""Entry point of the mini shop demo."""
from shop.models import Product, Customer
from shop.orders import create_order, checkout


def run_demo():
    """Create sample data, place an order and check out with a discount code."""
    laptop = Product("Laptop", 25000, stock=5)
    mouse = Product("Mouse", 500, stock=20)
    customer = Customer("Somchai", "somchai@example.com")
    order = create_order(customer, [(laptop, 1), (mouse, 2)])
    return checkout(order, discount_code="WELCOME10")


def main():
    print(run_demo())


if __name__ == "__main__":
    main()
