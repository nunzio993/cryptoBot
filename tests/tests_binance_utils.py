# tests/test_binance_utils.py
import pytest
from src.binance_utils import has_sufficient_balance

class DummyClient:
    def __init__(self, balances):
        self._balances = balances

    def get_account(self):
        return {
            'balances': [
                {'asset': k, 'free': str(v), 'locked': '0'}
                for k, v in self._balances.items()
            ]
        }

def test_balance_true():
    client = DummyClient({'USDC': 100.0})
    assert has_sufficient_balance(client, 'USDC', 50.0) is True

def test_balance_false():
    client = DummyClient({'USDC': 20.0})
    assert has_sufficient_balance(client, 'USDC', 50.0) is False

def test_balance_missing_asset():
    client = DummyClient({'BTC': 1.0})
    assert has_sufficient_balance(client, 'USDC', 1.0) is False

