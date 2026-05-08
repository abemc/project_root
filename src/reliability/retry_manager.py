import time
import logging
from functools import wraps
import random

logger = logging.getLogger(__name__)

class RetryManager:
    """
    Phase 19 Task 1: SLA & 信頼性確保
    指数バックオフを用いたリトライ管理。
    """

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    def execute(self, func, *args, **kwargs):
        """指数バックオフで関数を実行する。"""
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt == self.max_retries:
                    break
                
                # 指数バックオフ + ジッター
                delay = min(self.max_delay, self.base_delay * (2 ** attempt))
                jitter = delay * 0.1 * random.uniform(-1, 1)
                final_delay = max(0.1, delay + jitter)
                
                logger.warning(f"Retry attempt {attempt + 1}/{self.max_retries} after {final_delay:.2f}s due to: {e}")
                time.sleep(final_delay)
        
        logger.error(f"All retry attempts failed. Last error: {last_exception}")
        raise last_exception

def with_retry(max_retries=3, base_delay=1.0):
    """リトライ用のデコレータ。"""
    manager = RetryManager(max_retries, base_delay)
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return manager.execute(func, *args, **kwargs)
        return wrapper
    return decorator
