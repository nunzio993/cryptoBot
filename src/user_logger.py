"""
Per-user logging system with file rotation.
Only logs important events, not periodic checks.
"""
import logging
from logging.handlers import RotatingFileHandler
import os

# Cache dei logger per utente
_user_loggers = {}

def get_user_logger(user_id: int) -> logging.Logger:
    """Ritorna un logger dedicato all'utente"""
    if user_id in _user_loggers:
        return _user_loggers[user_id]
    
    os.makedirs("logs", exist_ok=True)
    
    logger = logging.getLogger(f"user_{user_id}")
    logger.setLevel(logging.INFO)
    
    # Evita duplicati se già configurato
    if not logger.handlers:
        handler = RotatingFileHandler(
            f"logs/user_{user_id}.log",
            maxBytes=5*1024*1024,  # 5MB
            backupCount=2  # Max 2 backup files
        )
        handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        logger.addHandler(handler)
    
    _user_loggers[user_id] = logger
    return logger


def log_event(user_id: int, event: str, **kwargs):
    """
    Log un evento importante per l'utente.
    
    Usage:
        log_event(1, "ORDER_EXECUTED", id=220, symbol="BNBUSDC", price=660.5)
        log_event(1, "ERROR", message="Failed to place order")
    """
    logger = get_user_logger(user_id)
    details = " | ".join(f"{k}={v}" for k, v in kwargs.items())
    logger.info(f"{event} | {details}" if details else event)
