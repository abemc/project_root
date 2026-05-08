"""
Phase 7 RAG エラー処理・ロギング・監視機構
- 包括的なエラー処理
- 構造化ロギング
- 監視・メトリクス収集
- デバッグトレース機能
"""

import logging
import sys
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path


class LogLevel(Enum):
    """ログレベル定義"""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


@dataclass
class ErrorContext:
    """エラーコンテキスト"""
    error_type: str
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    traceback: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    recovery_suggestion: str = ""
    
    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            'type': self.error_type,
            'message': self.message,
            'timestamp': self.timestamp,
            'traceback': self.traceback,
            'context': self.context,
            'recovery': self.recovery_suggestion
        }
    
    def to_json(self) -> str:
        """JSON形式に変換"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass
class LogEntry:
    """ログエントリ"""
    timestamp: str
    level: str
    component: str
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    
    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            'timestamp': self.timestamp,
            'level': self.level,
            'component': self.component,
            'message': self.message,
            'context': self.context,
            'duration_ms': self.duration_ms
        }


class Phase7Logger:
    """Phase 7統合ロギングシステム"""
    
    def __init__(
        self,
        name: str,
        log_file: Optional[Path] = None,
        log_level: LogLevel = LogLevel.INFO,
        enable_console: bool = True,
        enable_file: bool = True
    ):
        """
        Args:
            name: ロガー名
            log_file: ログファイルパス
            log_level: ログレベル
            enable_console: コンソール出力有効化
            enable_file: ファイル出力有効化
        """
        self.name = name
        self.log_file = log_file
        self.log_level = log_level
        self.enable_console = enable_console
        self.enable_file = enable_file
        
        # ロガー設定
        self.logger = logging.getLogger(name)
        self.logger.setLevel(log_level.value)
        
        # コンソールハンドラ
        if enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(log_level.value)
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)
        
        # ファイルハンドラ
        if enable_file and log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(log_level.value)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
        
        # ログエントリ履歴
        self.log_history: List[LogEntry] = []
        self.max_history = 1000
    
    def _add_to_history(
        self,
        level: str,
        message: str,
        context: Dict[str, Any] = None,
        duration_ms: Optional[float] = None
    ) -> None:
        """ログ履歴に追加"""
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level=level,
            component=self.name,
            message=message,
            context=context or {},
            duration_ms=duration_ms
        )
        self.log_history.append(entry)
        
        # 履歴サイズ制限
        if len(self.log_history) > self.max_history:
            self.log_history = self.log_history[-self.max_history:]
    
    def debug(self, message: str, context: Dict[str, Any] = None) -> None:
        """デバッグログ"""
        self.logger.debug(message)
        self._add_to_history('DEBUG', message, context)
    
    def info(self, message: str, context: Dict[str, Any] = None) -> None:
        """情報ログ"""
        self.logger.info(message)
        self._add_to_history('INFO', message, context)
    
    def warning(self, message: str, context: Dict[str, Any] = None) -> None:
        """警告ログ"""
        self.logger.warning(message)
        self._add_to_history('WARNING', message, context)
    
    def error(self, message: str, context: Dict[str, Any] = None) -> None:
        """エラーログ"""
        self.logger.error(message)
        self._add_to_history('ERROR', message, context)
    
    def critical(self, message: str, context: Dict[str, Any] = None) -> None:
        """クリティカルログ"""
        self.logger.critical(message)
        self._add_to_history('CRITICAL', message, context)
    
    def get_history(self, level: Optional[str] = None) -> List[Dict]:
        """ログ履歴取得"""
        if level:
            return [
                entry.to_dict()
                for entry in self.log_history
                if entry.level == level
            ]
        return [entry.to_dict() for entry in self.log_history]
    
    def export_history(self, output_file: Path) -> None:
        """ログ履歴をファイルにエクスポート"""
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(
                self.get_history(),
                f,
                ensure_ascii=False,
                indent=2
            )
        self.info(f"ログ履歴をエクスポート: {output_file}")
    
    def clear_history(self) -> None:
        """ログ履歴クリア"""
        self.log_history.clear()


class ErrorHandler:
    """統一エラーハンドラー"""
    
    # エラー復旧戦略マッピング
    ERROR_RECOVERY = {
        'QueryProcessingError': {
            'message': 'クエリ処理エラーが発生しました',
            'recovery': 'クエリを簡潔にして再実行してください'
        },
        'RetrievalError': {
            'message': 'ドキュメント取得エラーが発生しました',
            'recovery': 'コーパスインデックスを確認してください'
        },
        'KnowledgeIntegrationError': {
            'message': '知識統合エラーが発生しました',
            'recovery': 'ドメイン設定を確認してください'
        },
        'GenerationError': {
            'message': '応答生成エラーが発生しました',
            'recovery': 'LLM接続を確認してください'
        },
        'CacheError': {
            'message': 'キャッシュエラーが発生しました',
            'recovery': 'キャッシュをクリアしてから再実行してください'
        }
    }
    
    @staticmethod
    def handle(
        error: Exception,
        operation: str,
        logger: Phase7Logger,
        context: Dict[str, Any] = None,
        reraise: bool = False
    ) -> ErrorContext:
        """
        エラー処理
        
        Args:
            error: 例外オブジェクト
            operation: 操作名
            logger: ロガーインスタンス
            context: コンテキスト情報
            reraise: 例外を再発生させるか
        
        Returns:
            ErrorContext: エラーコンテキスト
        """
        error_type = type(error).__name__
        message = str(error)
        tb = traceback.format_exc()
        
        # 復旧提案を取得
        recovery_info = ErrorHandler.ERROR_RECOVERY.get(
            error_type,
            {
                'message': f'{error_type}が発生しました',
                'recovery': 'ログを確認してエラーを診断してください'
            }
        )
        
        # エラーコンテキスト生成
        error_context = ErrorContext(
            error_type=error_type,
            message=message,
            traceback=tb,
            context=context or {'operation': operation},
            recovery_suggestion=recovery_info['recovery']
        )
        
        # ログ出力
        logger.error(
            f"{recovery_info['message']} ({operation})",
            context={
                'error_type': error_type,
                'operation': operation,
                'message': message,
                'recovery': error_context.recovery_suggestion,
                **(context or {})
            }
        )
        
        # 詳細トレース出力（デバッグ用）
        logger.debug(f"トレース情報:\n{tb}")
        
        # 例外を再発生させるか
        if reraise:
            raise error
        
        return error_context
    
    @staticmethod
    def handle_async(
        coro,
        operation: str,
        logger: Phase7Logger,
        context: Dict[str, Any] = None
    ):
        """非同期関数のエラーハンドリングデコレーター"""
        async def wrapper(*args, **kwargs):
            try:
                return await coro(*args, **kwargs)
            except Exception as e:
                ErrorHandler.handle(e, operation, logger, context, reraise=False)
                return None
        return wrapper


class PerformanceMonitor:
    """パフォーマンス監視"""
    
    def __init__(self, logger: Phase7Logger):
        """
        Args:
            logger: ロガーインスタンス
        """
        self.logger = logger
        self.metrics: Dict[str, List[float]] = {}
        self.operation_times: Dict[str, List[float]] = {}
    
    def record_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = ""
    ) -> None:
        """メトリクス記録"""
        if metric_name not in self.metrics:
            self.metrics[metric_name] = []
        
        self.metrics[metric_name].append(value)
        
        if len(self.metrics[metric_name]) % 10 == 0:
            avg = sum(self.metrics[metric_name]) / len(self.metrics[metric_name])
            self.logger.debug(
                f"{metric_name}平均: {avg:.2f}{unit}",
                context={'metric': metric_name, 'average': avg}
            )
    
    def record_operation_time(
        self,
        operation: str,
        duration_ms: float
    ) -> None:
        """操作時間記録"""
        if operation not in self.operation_times:
            self.operation_times[operation] = []
        
        self.operation_times[operation].append(duration_ms)
    
    def get_summary(self) -> Dict[str, Any]:
        """パフォーマンスサマリー"""
        summary = {
            'metrics': {},
            'operations': {}
        }
        
        # メトリクスサマリー
        for name, values in self.metrics.items():
            if values:
                summary['metrics'][name] = {
                    'count': len(values),
                    'min': min(values),
                    'max': max(values),
                    'avg': sum(values) / len(values)
                }
        
        # 操作時間サマリー
        for op, times in self.operation_times.items():
            if times:
                summary['operations'][op] = {
                    'count': len(times),
                    'min_ms': min(times),
                    'max_ms': max(times),
                    'avg_ms': sum(times) / len(times)
                }
        
        return summary
    
    def print_report(self) -> None:
        """パフォーマンスレポート表示"""
        summary = self.get_summary()
        
        print("\n📊 パフォーマンスレポート")
        
        if summary['metrics']:
            print("\n【メトリクス】")
            for name, stats in summary['metrics'].items():
                print(f"  {name}:")
                print(f"    件数: {stats['count']}")
                print(f"    平均: {stats['avg']:.2f}")
                print(f"    範囲: {stats['min']:.2f} - {stats['max']:.2f}")
        
        if summary['operations']:
            print("\n【操作時間】")
            for op, times in summary['operations'].items():
                print(f"  {op}:")
                print(f"    件数: {times['count']}")
                print(f"    平均: {times['avg_ms']:.1f}ms")
                print(f"    範囲: {times['min_ms']:.1f}ms - {times['max_ms']:.1f}ms")
