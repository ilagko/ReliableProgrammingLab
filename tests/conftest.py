import pytest
from cart import ShoppingCart
from repository import StoreRepository
from setup_db import initialize


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / 'shop.db'
    initialize(path)
    return StoreRepository(path)


@pytest.fixture
def cart(repo):
    return ShoppingCart('student', repo)
