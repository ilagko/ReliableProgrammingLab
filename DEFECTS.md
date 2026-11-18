# 8 bugs and their fixes

## 1. Negative item quantities
**File:** `cart.py`

The cart accepted amounts like `-2`. Removing a negative amount could even add items.

**Fix:** Only allow whole numbers greater than zero when adding or removing items.

## 2. Adding more items than the store has
**File:** `cart.py`

If the store had 5 laptops, a customer could add 3 and then another 3. The cart would contain 6.

**Fix:** Check the number already in the cart plus the number being added.

## 3. Money rounding errors
**Files:** `models.py`, `cart.py`

Ordinary decimal numbers in Python can produce small rounding errors when calculating prices.

**Fix:** Use `Decimal` for money and round to two decimal places. For example, a discounted total of $0.135 becomes $0.14.

## 4. Wrong totals after using a coupon
**File:** `cart.py`

Applying the same coupon twice gave extra discounts. Changing the cart after applying a coupon could leave the old total. `SAVE15` could also make a small order cost less than $0.

**Fix:** Apply one coupon to the current subtotal each time. Never let the total go below $0.

## 5. Loading a cart added the same items again
**File:** `cart.py`

Loading a saved cart twice could turn 2 cables into 4 cables.

**Fix:** Replace the current cart with the saved cart instead of adding the saved items again.

## 6. Customers could see other customers' orders
**File:** `repository.py`

The order list returned all orders, even when a particular customer was requested.

**Fix:** Return only orders belonging to that customer.

## 7. Failed checkout changed stock and emptied the cart
**Files:** `checkout.py`, `repository.py`

Stock was reduced before payment. If payment failed, the customer could lose their cart and the store could lose stock without making a sale.

**Fix:** Check stock again at checkout. Undo stock changes if payment fails, and keep the customer's cart. Only clear the cart after a successful purchase is saved.

## 8. Repeated checkout could charge twice
**File:** `checkout.py`

Sending the same checkout request again could create another order and another charge.

**Fix:** Save the result using a request ID. If that customer sends the same ID again, return the saved result without charging again.

## Choices made

- Only one coupon can be used at a time. A new coupon replaces the old one.
- There are no tax or shipping charges, so `FREESHIP` does not change the total. A $0 order is allowed.
- Loading a cart uses current prices and clears its coupon. If a saved item is unavailable, loading fails and leaves the current cart alone.
- A new purchase needs a new request ID. A declined payment can be retried with a new ID. If a payment error leaves the outcome unclear, check it before trying again.
- Use a fresh database. The original payment simulator is unchanged.

## Tests

There are exactly **12 tests** in `tests/test_order_processing.py`. They use temporary databases and fake payments.

Run them with:

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

Result: **12 passed**.

GitHub Actions runs the tests on every push and pull request using Python 3.10 and 3.13.

[Successful test run](https://github.com/ilagko/ReliableProgrammingLab/actions/runs/44385426250)
