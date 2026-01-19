"""
Trading utilities for quantity and price formatting.
Universally compatible with all exchanges (Binance, Bybit, future exchanges).
Uses Decimal for precision and avoids scientific notation.
"""
from decimal import Decimal, ROUND_DOWN


def round_to_step(value: float, step: float) -> float:
    """
    Round a value DOWN to the nearest multiple of step.
    Uses Decimal for precision, returns float for calculations.
    
    Args:
        value: The value to round (quantity or price)
        step: The step size (LOT_SIZE stepSize or PRICE_FILTER tickSize)
    
    Returns:
        float rounded down to step
    
    Example:
        round_to_step(0.1234567, 0.001) -> 0.123
        round_to_step(123.456, 0.01) -> 123.45
    """
    step_dec = Decimal(str(step))
    val_dec = Decimal(str(value))
    result = (val_dec / step_dec).quantize(Decimal('1'), rounding=ROUND_DOWN) * step_dec
    return float(result)


def format_quantity(qty: float, step_size: float) -> str:
    """
    Format quantity for exchange API (no trailing zeros, no scientific notation).
    
    Args:
        qty: Quantity to format
        step_size: LOT_SIZE stepSize from symbol info
    
    Returns:
        String formatted for exchange API
    
    Example:
        format_quantity(0.12300000, 0.001) -> "0.123"
        format_quantity(100.0, 1.0) -> "100"
    """
    step = Decimal(str(step_size))
    qty_dec = Decimal(str(qty)).quantize(step, rounding=ROUND_DOWN)
    # Use format to avoid scientific notation, then strip zeros
    result = f"{float(qty_dec):.10f}".rstrip('0').rstrip('.')
    return result


def format_price(price: float, tick_size: float) -> str:
    """
    Format price for exchange API (no trailing zeros, no scientific notation).
    
    Args:
        price: Price to format
        tick_size: PRICE_FILTER tickSize from symbol info
    
    Returns:
        String formatted for exchange API
    
    Example:
        format_price(12345.67890, 0.01) -> "12345.67"
        format_price(0.00012345, 0.00000001) -> "0.00012345"
    """
    tick = Decimal(str(tick_size))
    # Handle both Decimal and float inputs
    if isinstance(price, Decimal):
        price_dec = price
    else:
        price_dec = Decimal(str(float(price)))
    
    result = price_dec.quantize(tick, rounding=ROUND_DOWN)
    # Use format to avoid scientific notation, then strip zeros
    return f"{float(result):.10f}".rstrip('0').rstrip('.')
