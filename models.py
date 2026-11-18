"""Domain objects and shared validation; all monetary values are Decimal."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def money(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0:
            raise ValueError('Money must be finite and nonnegative')
        return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError('Invalid monetary value') from exc


def positive_quantity(value):
    if type(value) is not int or value <= 0:
        raise ValueError('Quantity must be a positive integer')
    return value


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    price: Decimal
    stock: int

    def __post_init__(self):
        object.__setattr__(self, 'price', money(self.price))
        if type(self.stock) is not int or self.stock < 0:
            raise ValueError('Stock must be a nonnegative integer')


@dataclass(frozen=True)
class CartLine:
    sku: str
    name: str
    unit_price: Decimal
    quantity: int

    def __post_init__(self):
        object.__setattr__(self, 'unit_price', money(self.unit_price))
        positive_quantity(self.quantity)


@dataclass(frozen=True)
class OrderResult:
    order_id: int | None
    status: str
    total: Decimal
