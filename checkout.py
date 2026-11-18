"""Transactional checkout using the supplied simulated gateway."""
from decimal import Decimal
from models import OrderResult
from repository import OutOfStock


class CheckoutService:
    def __init__(self, repository, payment_gateway):
        self.repository = repository
        self.payment_gateway = payment_gateway

    def checkout(self, cart, payment_token, request_id):
        if not isinstance(request_id, str) or not request_id.strip():
            raise ValueError('A nonempty request ID is required')
        if not isinstance(payment_token, str) or not payment_token.strip():
            raise ValueError('A simulated payment token is required')
        repo = self.repository
        with repo.transaction() as conn:
            previous = repo.get_order(cart.user_id, request_id, conn)
            if previous is not None:
                return previous
            if not cart.lines:
                return OrderResult(None, 'empty', Decimal('0.00'))
            amount = cart.total()
            # Reserve all stock atomically. Releasing this savepoint undoes every
            # decrement on stock failure, decline or an unexpected gateway error.
            conn.execute('SAVEPOINT inventory')
            try:
                for line in cart.lines:
                    repo.update_stock(line.sku, line.quantity, conn)
            except OutOfStock:
                conn.execute('ROLLBACK TO inventory')
                conn.execute('RELEASE inventory')
                return OrderResult(None, 'out_of_stock', amount)
            try:
                response = self.payment_gateway.charge(amount, payment_token)
                approved = response['approved']
                if type(approved) is not bool:
                    raise ValueError('Gateway approval must be boolean')
                status = 'paid' if approved else 'declined'
            except Exception:
                status = 'payment_error'
            if status != 'paid':
                conn.execute('ROLLBACK TO inventory')
            conn.execute('RELEASE inventory')
            order_id = repo.save_order(cart.user_id, amount, status, request_id, conn)
            if status == 'paid':
                repo.save_cart(cart.user_id, [], conn)
        # Only change the in-memory cart after the database commit succeeds.
        if status == 'paid':
            cart.lines.clear()
            cart.discount_code = None
        return OrderResult(order_id, status, amount)
