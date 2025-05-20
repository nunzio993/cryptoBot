import pytest
from src.symbols import normalize_quantity

@pytest.mark.parametrize("qty,step,min_q,max_q,expected", [
    (0.0057, 0.001, 0.001, 10, 0.005),
    (1.999, 0.01, 0.01, 100, 1.99),
    (5.0,   0.1,  0.1,   10,   5.0),
])
def test_normalize_ok(qty, step, min_q, max_q, expected):
    assert normalize_quantity(qty, step, min_q, max_q) == expected

@pytest.mark.parametrize("qty,step,min_q,max_q", [
    (0.0005, 0.001, 0.001, 10),  # sotto min_qty
    (20,     0.01,  0.01, 10),   # oltre max_qty
])
def test_normalize_error(qty, step, min_q, max_q):
    with pytest.raises(ValueError):
        normalize_quantity(qty, step, min_q, max_q)
