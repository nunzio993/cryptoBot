"""
Retry utilities for exchange API calls with exponential backoff.
"""

import time
import logging
from functools import wraps
from typing import Callable, TypeVar, Any

logger = logging.getLogger('retry')

T = TypeVar('T')


def retry_on_failure(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = (Exception,)
) -> Callable:
    """
    Decorator that retries a function on failure with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff
        retryable_exceptions: Tuple of exceptions to retry on
    
    Usage:
        @retry_on_failure(max_retries=3)
        def call_api():
            return client.get_balance()
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"[RETRY] {func.__name__} failed after {max_retries} retries: {e}")
                        raise
                    
                    logger.warning(f"[RETRY] {func.__name__} attempt {attempt + 1}/{max_retries} failed: {e}, retrying in {delay:.1f}s")
                    time.sleep(delay)
                    delay = min(delay * exponential_base, max_delay)
            
            raise last_exception
        
        return wrapper
    return decorator


def retry_sync(
    func: Callable[..., T],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    retryable_exceptions: tuple = (Exception,),
    *args,
    **kwargs
) -> T:
    """
    Retry a function call with exponential backoff.
    
    Usage:
        result = retry_sync(client.get_balance, max_retries=3, asset="USDC")
    """
    delay = initial_delay
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except retryable_exceptions as e:
            last_exception = e
            
            if attempt == max_retries:
                logger.error(f"[RETRY] {func.__name__} failed after {max_retries} retries: {e}")
                raise
            
            logger.warning(f"[RETRY] {func.__name__} attempt {attempt + 1}/{max_retries} failed: {e}, retrying in {delay:.1f}s")
            time.sleep(delay)
            delay = min(delay * 2, 30.0)
    
    raise last_exception
