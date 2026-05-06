"""
Retry Manager Implementation

リトライ・タイムアウト戦略の実装
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Callable, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import asyncio
import logging
import random

logger = logging.getLogger(__name__)


class BackoffStrategy(Enum):
    """バックオフ戦略"""
    FIXED = "fixed"              # 固定間隔
    LINEAR = "linear"            # 線形増加
    EXPONENTIAL = "exponential"  # 指数関数的増加
    RANDOM = "random"            # ランダム


@dataclass
class RetryConfig:
    """リトライ設定"""
    max_retries: int = 3
    initial_delay: float = 1.0               # 初期遅延（秒）
    max_delay: float = 60.0                 # 最大遅延（秒）
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    jitter: bool = True                      # ジッターを追加
    timeout: float = 30.0                   # タイムアウト（秒）
    
    # リトライ対象外の例外
    fatal_exceptions: Tuple[type, ...] = field(
        default_factory=lambda: (ValueError, TypeError)
    )


@dataclass
class RetryMetrics:
    """リトライメトリクス"""
    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    total_retries: int = 0
    timeout_count: int = 0
    
    def get_success_rate(self) -> float:
        """成功率を取得"""
        if self.total_attempts == 0:
            return 100.0
        return (self.successful_attempts / self.total_attempts) * 100
    
    def get_average_retry_count(self) -> float:
        """平均リトライ回数を取得"""
        if self.successful_attempts == 0:
            return 0.0
        return self.total_retries / self.successful_attempts


class RetryManager:
    """
    リトライ・タイムアウト管理
    
    複数のリトライ戦略と適応的なバックオフを提供
    """
    
    def __init__(self, config: RetryConfig):
        """初期化"""
        self.config = config
        self.metrics = RetryMetrics()
    
    async def execute(
        self, 
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        リトライ機能付きで関数を実行
        
        Args:
            func: 実行する関数
            *args: 位置引数
            **kwargs: キーワード引数
            
        Returns:
            関数の実行結果
            
        Raises:
            最後の例外
        """
        last_exception: Optional[Exception] = None
        attempt = 0
        
        while attempt <= self.config.max_retries:
            try:
                attempt += 1
                self.metrics.total_attempts += 1
                
                logger.debug(f"Attempt {attempt}/{self.config.max_retries + 1}")
                
                # タイムアウト付きで実行
                if asyncio.iscoroutinefunction(func):
                    result = await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=self.config.timeout
                    )
                else:
                    result = func(*args, **kwargs)
                
                self.metrics.successful_attempts += 1
                return result
                
            except asyncio.TimeoutError as e:
                last_exception = e
                self.metrics.timeout_count += 1
                logger.warning(f"Timeout on attempt {attempt}")
                
            except self.config.fatal_exceptions as e:
                # 致命的な例外はリトライしない
                self.metrics.failed_attempts += 1
                logger.error(f"Fatal exception: {e}")
                raise
                
            except Exception as e:
                last_exception = e
                logger.debug(f"Exception on attempt {attempt}: {e}")
            
            # 最後の試行でない場合、待機
            if attempt <= self.config.max_retries:
                delay = self._calculate_delay(attempt - 1)
                self.metrics.total_retries += 1
                logger.debug(f"Retrying after {delay:.2f}s...")
                await asyncio.sleep(delay)
        
        self.metrics.failed_attempts += 1
        if last_exception:
            raise last_exception
        raise RuntimeError("Execution failed after all retries")
    
    def _calculate_delay(self, retry_count: int) -> float:
        """バックオフ遅延を計算"""
        if self.config.backoff_strategy == BackoffStrategy.FIXED:
            delay = self.config.initial_delay
            
        elif self.config.backoff_strategy == BackoffStrategy.LINEAR:
            delay = self.config.initial_delay * (retry_count + 1)
            
        elif self.config.backoff_strategy == BackoffStrategy.EXPONENTIAL:
            delay = self.config.initial_delay * (2 ** retry_count)
            
        elif self.config.backoff_strategy == BackoffStrategy.RANDOM:
            delay = random.uniform(
                self.config.initial_delay,
                self.config.initial_delay * (retry_count + 1)
            )
        else:
            delay = self.config.initial_delay
        
        # 最大遅延を適用
        delay = min(delay, self.config.max_delay)
        
        # ジッターを追加
        if self.config.jitter:
            jitter_amount = delay * random.uniform(0, 0.1)
            delay += jitter_amount
        
        return delay
    
    def get_metrics(self) -> RetryMetrics:
        """メトリクスを取得"""
        return self.metrics
    
    def reset_metrics(self) -> None:
        """メトリクスをリセット"""
        self.metrics = RetryMetrics()


class RetryDecorator:
    """リトライのためのデコレーター"""
    
    def __init__(self, config: RetryConfig):
        """初期化"""
        self.manager = RetryManager(config)
    
    def __call__(self, func: Callable) -> Callable:
        """デコレーターとして機能"""
        async def async_wrapper(*args, **kwargs):
            return await self.manager.execute(func, *args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            # 同期関数の場合、asyncioイベントループを作成
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(
                    self.manager.execute(func, *args, **kwargs)
                )
            finally:
                loop.close()
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper


def retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL,
) -> Callable:
    """
    リトライデコレーター
    
    使用例:
        @retry(max_retries=3, backoff_strategy=BackoffStrategy.EXPONENTIAL)
        async def my_function():
            ...
    """
    config = RetryConfig(
        max_retries=max_retries,
        initial_delay=initial_delay,
        backoff_strategy=backoff_strategy,
    )
    return RetryDecorator(config)


class TimeoutManager:
    """タイムアウト管理"""
    
    def __init__(self, timeout: float = 30.0):
        """初期化"""
        self.timeout = timeout
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """タイムアウト付きで関数を実行"""
        try:
            if asyncio.iscoroutinefunction(func):
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.timeout
                )
            else:
                return func(*args, **kwargs)
        except asyncio.TimeoutError:
            logger.error(f"Function execution timed out after {self.timeout}s")
            raise
