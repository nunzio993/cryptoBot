# src/binance_utils.py
import logging
from binance.client import Client

logger = logging.getLogger(__name__)

def has_sufficient_balance(client: Client, asset: str, required: float) -> bool:
    """
    Restituisce True se sul conto c'è almeno `required` di `asset` (campo 'free').
    """
    try:
        logger.debug(f"[DEBUG BALANCE CHECK] asset={asset}, required={required:.2f}")
        account = client.get_account()
        balances = {b['asset']: float(b['free']) for b in account.get('balances', [])}
        available = balances.get(asset, 0.0)
        logger.debug(f"[BALANCE] {asset}: available={available}, required={required}")
        return available >= required
    except Exception as e:
        logger.error(f"[BALANCE] errore verifica saldo {asset}: {e}")
        return False

