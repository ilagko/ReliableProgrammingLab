"""Shopping cart with fresh totals and one non-stacking coupon."""
from dataclasses import replace
from decimal import Decimal
from models import CartLine, money, positive_quantity


class ShoppingCart:
    def __init__(self, user_id, repository):
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError('A user ID is required')
        self.user_id = user_id
        self.repository = repository
        self.lines = []
        self.discount_code = None

    def add_item(self, sku, quantity):
        positive_quantity(quantity)
        product = self.repository.get_product(sku)
        existing = next((line for line in self.lines if line.sku == sku), None)
        combined = quantity + (existing.quantity if existing else 0)
        if product is None or combined > product.stock:
            return False
        if existing:
            self.lines[self.lines.index(existing)] = replace(existing, quantity=combined)
        else:
            self.lines.append(CartLine(sku, product.name, product.price, quantity))
        return True

    def remove_item(self, sku, quantity=None):
        if quantity is not None:
            positive_quantity(quantity)
        for index, line in enumerate(self.lines):
            if line.sku == sku:
                if quantity is None or quantity >= line.quantity:
                    self.lines.pop(index)
                else:
                    self.lines[index] = replace(line, quantity=line.quantity - quantity)
                return True
        return False

    def subtotal(self):
        return sum((line.unit_price * line.quantity for line in self.lines), Decimal('0.00'))

    def total(self):
        amount = self.subtotal()
        if self.discount_code == 'WELCOME10':
            amount *= Decimal('0.90')
        elif self.discount_code == 'STUDENT20':
            amount *= Decimal('0.80')
        elif self.discount_code == 'SAVE15':
            amount -= Decimal('15.00')
        return money(max(Decimal('0'), amount))

    def apply_discount(self, code):
        if code not in ('WELCOME10', 'STUDENT20', 'SAVE15', 'FREESHIP'):
            return False
        self.discount_code = code
        return True

    def load(self):
        # Build separately so an unavailable saved item cannot partially replace a cart.
        loaded = ShoppingCart(self.user_id, self.repository)
        for sku, quantity in self.repository.get_saved_cart(self.user_id):
            if not loaded.add_item(sku, quantity):
                raise ValueError(f'Saved product unavailable: {sku}')
        self.lines = loaded.lines
        self.discount_code = None

    def save(self):
        self.repository.save_cart(self.user_id, self.lines)
