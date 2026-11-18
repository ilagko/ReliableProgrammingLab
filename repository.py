"""SQLite persistence with parameterized queries and explicit transactions."""
from contextlib import contextmanager
import sqlite3
from models import Product, OrderResult, money, positive_quantity


class OutOfStock(ValueError):
    pass


class StoreRepository:
    def __init__(self, db_path='shop.db'):
        self.db_path = db_path

    def connect(self):
        return sqlite3.connect(self.db_path, timeout=2)

    @contextmanager
    def transaction(self):
        conn = self.connect()
        try:
            conn.execute('BEGIN IMMEDIATE')
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def session(self, conn=None):
        if conn is not None:
            yield conn
        else:
            with self.transaction() as owned:
                yield owned

    def get_product(self, sku, conn=None):
        with self.session(conn) as db:
            row = db.execute('SELECT sku, name, price, stock FROM products WHERE sku = ?', (sku,)).fetchone()
            return Product(*row) if row else None

    def get_saved_cart(self, user_id):
        with self.session() as db:
            return db.execute('SELECT sku, quantity FROM saved_cart WHERE user_id = ? ORDER BY sku', (user_id,)).fetchall()

    def save_cart(self, user_id, lines, conn=None):
        # Validate before deleting existing rows. SQL failures also roll back the replacement.
        rows = [(user_id, line.sku, positive_quantity(line.quantity)) for line in lines]
        with self.session(conn) as db:
            db.execute('DELETE FROM saved_cart WHERE user_id = ?', (user_id,))
            db.executemany('INSERT INTO saved_cart(user_id, sku, quantity) VALUES (?, ?, ?)', rows)

    def update_stock(self, sku, quantity, conn=None):
        positive_quantity(quantity)
        with self.session(conn) as db:
            result = db.execute('UPDATE products SET stock = stock - ? WHERE sku = ? AND stock >= ?',
                                (quantity, sku, quantity))
            if result.rowcount != 1:
                raise OutOfStock(sku)

    def save_order(self, user_id, amount, status, request_id, conn=None):
        with self.session(conn) as db:
            result = db.execute('INSERT INTO orders(user_id, amount, status, request_id) VALUES (?, ?, ?, ?)',
                                (user_id, str(money(amount)), status, request_id))
            return result.lastrowid

    def get_order(self, user_id, request_id, conn=None):
        with self.session(conn) as db:
            row = db.execute('SELECT id, status, amount FROM orders WHERE user_id = ? AND request_id = ?',
                             (user_id, request_id)).fetchone()
            return OrderResult(row[0], row[1], money(row[2])) if row else None

    def list_orders(self, user_id):
        with self.session() as db:
            rows = db.execute('SELECT id, user_id, amount, status FROM orders WHERE user_id = ? ORDER BY id DESC',
                              (user_id,)).fetchall()
            return [(row[0], row[1], money(row[2]), row[3]) for row in rows]
