"""Twelve focused unit tests for the eight defects listed in DEFECTS.md."""
from decimal import Decimal
from unittest.mock import Mock

import pytest

from cart import ShoppingCart
from checkout import CheckoutService
from models import Product
from payments import FakePaymentGateway


def test_add_rejects_invalid_quantity(cart):
    with pytest.raises(ValueError, match='positive integer'):
        cart.add_item('USB-01', -1)
    assert cart.lines == []


def test_remove_validates_quantity_and_removes_items(cart):
    cart.add_item('USB-01', 3)
    with pytest.raises(ValueError, match='positive integer'):
        cart.remove_item('USB-01', -1)
    assert cart.lines[0].quantity == 3
    assert cart.remove_item('USB-01', 1)
    assert cart.lines[0].quantity == 2
    assert cart.remove_item('USB-01')
    assert cart.lines == []


def test_duplicate_additions_respect_combined_stock(cart):
    assert cart.add_item('LAP-01', 3)
    assert not cart.add_item('LAP-01', 3)
    assert cart.lines[0].quantity == 3
    assert cart.add_item('LAP-01', 2)
    assert len(cart.lines) == 1
    assert cart.lines[0].quantity == 5


def test_money_uses_decimal_and_rounds_half_up():
    repository = Mock()
    repository.get_product.return_value = Product('SMALL', 'Small item', '0.05', 10)
    cart = ShoppingCart('student', repository)
    cart.add_item('SMALL', 3)
    assert cart.subtotal() == Decimal('0.15')
    cart.apply_discount('WELCOME10')
    assert cart.total() == Decimal('0.14')


def test_discount_does_not_stack_and_tracks_cart_edits(cart):
    cart.add_item('MOU-01', 2)
    cart.apply_discount('WELCOME10')
    cart.apply_discount('WELCOME10')
    assert cart.total() == Decimal('53.91')
    cart.remove_item('MOU-01', 1)
    assert cart.total() == Decimal('26.96')
    cart.apply_discount('STUDENT20')
    assert cart.total() == Decimal('23.96')


def test_fixed_discount_cannot_make_total_negative(cart):
    cart.apply_discount('SAVE15')
    assert cart.total() == Decimal('0.00')
    cart.add_item('USB-01', 1)
    assert cart.total() == Decimal('0.00')
    cart.add_item('USB-01', 1)
    assert cart.total() == Decimal('4.98')


def test_loading_saved_cart_twice_does_not_duplicate_items(cart):
    cart.add_item('USB-01', 2)
    cart.save()
    cart.add_item('MOU-01', 1)
    cart.load()
    cart.load()
    assert [(line.sku, line.quantity) for line in cart.lines] == [('USB-01', 2)]
    assert cart.subtotal() == Decimal('19.98')


def test_repository_queries_keep_users_separate(repo):
    quoted_user = "O'Brien"
    cart = ShoppingCart(quoted_user, repo)
    cart.add_item('USB-01', 1)
    cart.save()
    assert repo.get_saved_cart(quoted_user) == [('USB-01', 1)]
    assert repo.get_saved_cart('other') == []
    order_id = repo.save_order(quoted_user, '9.99', 'paid', 'r1')
    repo.save_order('other', '29.95', 'paid', 'r2')
    assert repo.list_orders(quoted_user) == [(order_id, quoted_user, Decimal('9.99'), 'paid')]


def test_empty_checkout_does_not_charge(cart, repo):
    gateway = FakePaymentGateway()
    result = CheckoutService(repo, gateway).checkout(cart, 'TEST', 'r1')
    assert result.status == 'empty'
    assert result.order_id is None
    assert result.total == Decimal('0.00')
    assert gateway.calls == []
    assert repo.list_orders(cart.user_id) == []


def test_checkout_rechecks_stock_and_rolls_back_all_items(cart, repo):
    gateway = FakePaymentGateway()
    cart.add_item('USB-01', 2)
    cart.add_item('LAP-01', 2)
    repo.update_stock('LAP-01', 4)
    result = CheckoutService(repo, gateway).checkout(cart, 'TEST', 'r1')
    assert result.status == 'out_of_stock'
    assert repo.get_product('USB-01').stock == 50
    assert repo.get_product('LAP-01').stock == 1
    assert gateway.calls == []
    assert len(cart.lines) == 2
    assert repo.list_orders(cart.user_id) == []


def test_failed_payments_preserve_stock_and_saved_cart(cart, repo):
    cart.add_item('MOU-01', 2)
    cart.apply_discount('WELCOME10')
    cart.save()
    declined = CheckoutService(repo, FakePaymentGateway(should_approve=False))
    assert declined.checkout(cart, 'TEST', 'declined-request').status == 'declined'
    assert repo.get_product('MOU-01').stock == 20
    assert cart.lines[0].quantity == 2
    assert repo.get_saved_cart(cart.user_id) == [('MOU-01', 2)]

    broken_gateway = Mock()
    broken_gateway.charge.side_effect = RuntimeError('Simulated gateway error')
    failed = CheckoutService(repo, broken_gateway)
    result = failed.checkout(cart, 'TEST', 'error-request')
    assert result.status == 'payment_error'
    assert failed.checkout(cart, 'TEST', 'error-request') == result
    broken_gateway.charge.assert_called_once()
    assert repo.get_product('MOU-01').stock == 20
    assert cart.lines[0].quantity == 2
    assert cart.discount_code == 'WELCOME10'
    assert repo.get_saved_cart(cart.user_id) == [('MOU-01', 2)]


def test_successful_checkout_is_idempotent(cart, repo):
    gateway = FakePaymentGateway()
    cart.add_item('MOU-01', 2)
    cart.apply_discount('WELCOME10')
    cart.save()
    first = CheckoutService(repo, gateway).checkout(cart, 'TEST', 'r1')
    assert first.status == 'paid'
    assert first.total == Decimal('53.91')
    assert cart.lines == []
    assert cart.discount_code is None
    assert repo.get_saved_cart(cart.user_id) == []

    # Recreate both objects to verify that deduplication is stored in SQLite.
    new_cart = ShoppingCart(cart.user_id, repo)
    second = CheckoutService(repo, gateway).checkout(new_cart, 'TEST', 'r1')
    assert second == first
    assert gateway.calls == [(Decimal('53.91'), 'TEST')]
    assert repo.get_product('MOU-01').stock == 18
    assert len(repo.list_orders(cart.user_id)) == 1
