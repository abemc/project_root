"""
Fallback Chain: エラーからの自動復帰戦略

Error Learning と統合して、類似エラーから復帰案を取得し、
段階的なフォールバック戦略を実行。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class FallbackStrategy(Enum):
    """フォールバック戦略"""
    RETRY_SAME = "retry_same"  # 同じツール・パラメータで再試行
    RETRY_MODIFIED = "retry_modified"  # 修正されたパラメータで再試行
    ALTERNATIVE_TOOL = "alternative_tool"  # 代替ツールに変更
    DEGRADE_QUALITY = "degrade_quality"  # 品質を落として簡易版を実行
    MANUAL_INTERVENTION = "manual_intervention"  # ユーザー対応を要請
    SKIP_TASK = "skip_task"  # タスクをスキップ


@dataclass
class FallbackOption:
    """フォールバックオプション"""
    strategy: FallbackStrategy
    tool_name: Optional[str] = None  # 代替ツール（ALTERNATIVE_TOOL 時）
    modified_args: Optional[List[str]] = None  # 修正引数（RETRY_MODIFIED 時）
    confidence: float = 0.5  # このオプションの信頼度 (0-1)
    reason: str = ""  # フォールバック理由


@dataclass
class FallbackAttempt:
    """フォールバック試行"""
    attempt_number: int
    strategy: FallbackStrategy
    original_error: str
    tool_name: str
    args: List[str]
    result: Optional[Any] = None
    success: bool = False
    timestamp: datetime = None


class FallbackChain:
    """フォールバックチェーン"""
    
    def __init__(self, error_learner=None):
        """
        初期化
        
        Args:
            error_learner: ErrorLearner インスタンス（エラー復帰案取得用）
        """
        self.error_learner = error_learner
        self.fallback_history: List[FallbackAttempt] = []
        self.max_fallback_attempts = 5
        self.custom_strategies: Dict[str, Callable] = {}
        
        logger.info("FallbackChain initialized")
    
    def register_custom_strategy(
        self,
        strategy_name: str,
        strategy_func: Callable,
    ):
        """カスタムフォールバック戦略を登録"""
        self.custom_strategies[strategy_name] = strategy_func
        logger.info(f"Custom fallback strategy registered: {strategy_name}")
    
    def get_fallback_options(
        self,
        tool_name: str,
        args: List[str],
        error: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[FallbackOption]:
        """
        エラーからのフォールバックオプションを取得
        
        Args:
            tool_name: 失敗したツール名
            args: ツール引数
            error: エラーメッセージ
            context: コンテキスト
        
        Returns:
            フォールバックオプションリスト（優先度順）
        """
        options = []
        context = context or {}
        
        # 1. Error Learning から復帰案を取得
        if self.error_learner:
            similar_errors = self.error_learner.search_similar_errors(error)
            recovery_suggestions = self.error_learner.get_recovery_suggestions(error)
            
            logger.info(f"Found {len(recovery_suggestions)} recovery suggestions for error")
            
            # 復帰案をフォールバックオプションに変換
            for suggestion in recovery_suggestions:
                if 'modified_args' in suggestion:
                    options.append(FallbackOption(
                        strategy=FallbackStrategy.RETRY_MODIFIED,
                        tool_name=tool_name,
                        modified_args=suggestion.get('modified_args', args),
                        confidence=suggestion.get('confidence', 0.6),
                        reason=suggestion.get('description', 'Suggested by error learning'),
                    ))
                
                if 'alternative_tool' in suggestion:
                    options.append(FallbackOption(
                        strategy=FallbackStrategy.ALTERNATIVE_TOOL,
                        tool_name=suggestion['alternative_tool'],
                        confidence=suggestion.get('confidence', 0.5),
                        reason=suggestion.get('description', 'Alternative tool suggestion'),
                    ))
        
        # 2. 標準フォールバック戦略を追加
        
        # 同じツール・パラメータで再試行（デフォルト）
        options.append(FallbackOption(
            strategy=FallbackStrategy.RETRY_SAME,
            tool_name=tool_name,
            confidence=0.4,
            reason="Retry with same parameters",
        ))
        
        # パラメータを修正して再試行
        modified_args = self._suggest_modified_args(tool_name, args, error)
        if modified_args != args:
            options.append(FallbackOption(
                strategy=FallbackStrategy.RETRY_MODIFIED,
                tool_name=tool_name,
                modified_args=modified_args,
                confidence=0.5,
                reason="Retry with suggested parameter modifications",
            ))
        
        # 代替ツールに変更
        alternative_tools = self._suggest_alternative_tools(tool_name, context)
        for alt_tool in alternative_tools:
            options.append(FallbackOption(
                strategy=FallbackStrategy.ALTERNATIVE_TOOL,
                tool_name=alt_tool,
                confidence=0.4,
                reason=f"Use alternative tool: {alt_tool}",
            ))
        
        # 品質を落とした簡易版を実行
        options.append(FallbackOption(
            strategy=FallbackStrategy.DEGRADE_QUALITY,
            tool_name=tool_name,
            confidence=0.6,
            reason="Execute simplified version with reduced quality",
        ))
        
        # ユーザーに対応を要請
        options.append(FallbackOption(
            strategy=FallbackStrategy.MANUAL_INTERVENTION,
            confidence=0.8,
            reason="Escalate to user for manual intervention",
        ))
        
        # タスクをスキップ
        options.append(FallbackOption(
            strategy=FallbackStrategy.SKIP_TASK,
            confidence=0.2,
            reason="Skip this task and continue with others",
        ))
        
        # 信頼度でソート（高い順）
        options.sort(key=lambda x: -x.confidence)
        
        return options
    
    def execute_fallback_chain(
        self,
        tool_name: str,
        args: List[str],
        error: str,
        tool_executor=None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[Any], List[FallbackAttempt]]:
        """
        フォールバックチェーンを実行
        
        Args:
            tool_name: 失敗したツール名
            args: ツール引数
            error: エラーメッセージ
            tool_executor: ToolExecutor インスタンス
            context: コンテキスト
        
        Returns:
            (成功, 結果, 試行履歴)
        """
        attempts = []
        
        if not tool_executor:
            logger.error("ToolExecutor not provided for fallback execution")
            return (False, None, attempts)
        
        # フォールバックオプションを取得
        options = self.get_fallback_options(tool_name, args, error, context)
        
        for attempt_num, option in enumerate(options[:self.max_fallback_attempts], 1):
            
            logger.info(
                f"Fallback attempt {attempt_num}/{self.max_fallback_attempts}: "
                f"{option.strategy.value} (confidence: {option.confidence:.1%})"
            )
            
            attempt = FallbackAttempt(
                attempt_number=attempt_num,
                strategy=option.strategy,
                original_error=error,
                tool_name=option.tool_name or tool_name,
                args=option.modified_args or args,
                timestamp=datetime.now(),
            )
            
            # 戦略に基づいて実行
            try:
                if option.strategy == FallbackStrategy.RETRY_SAME:
                    result = tool_executor.execute_tool(
                        tool_name=tool_name,
                        args=args,
                    )
                    attempt.result = result
                    attempt.success = (result.status == 'SUCCESS')
                
                elif option.strategy == FallbackStrategy.RETRY_MODIFIED:
                    result = tool_executor.execute_tool(
                        tool_name=tool_name,
                        args=option.modified_args or args,
                    )
                    attempt.result = result
                    attempt.success = (result.status == 'SUCCESS')
                
                elif option.strategy == FallbackStrategy.ALTERNATIVE_TOOL:
                    result = tool_executor.execute_tool(
                        tool_name=option.tool_name,
                        args=args,
                    )
                    attempt.result = result
                    attempt.success = (result.status == 'SUCCESS')
                
                elif option.strategy == FallbackStrategy.DEGRADE_QUALITY:
                    # 簡易版を実行（パラメータを制限）
                    degraded_args = self._degrade_args(args)
                    result = tool_executor.execute_tool(
                        tool_name=tool_name,
                        args=degraded_args,
                    )
                    attempt.result = result
                    attempt.success = (result.status == 'SUCCESS')
                
                elif option.strategy == FallbackStrategy.MANUAL_INTERVENTION:
                    # ユーザーに対応を要請（スキップ）
                    logger.warning("Manual intervention required")
                    attempt.success = False
                    # 実際の実装では、ここでユーザーに通知を送る
                
                elif option.strategy == FallbackStrategy.SKIP_TASK:
                    # タスクをスキップ
                    attempt.success = True
                    attempt.result = {'skipped': True}
                
            except Exception as e:
                logger.error(f"Fallback attempt {attempt_num} failed: {e}")
                attempt.success = False
                attempt.result = None
            
            attempts.append(attempt)
            
            # 成功したら終了
            if attempt.success:
                logger.info(f"Fallback succeeded on attempt {attempt_num}")
                self.fallback_history.extend(attempts)
                return (True, attempt.result, attempts)
        
        # 全フォールバック失敗
        logger.error(f"All {len(attempts)} fallback attempts failed")
        self.fallback_history.extend(attempts)
        return (False, None, attempts)
    
    def _suggest_modified_args(
        self,
        tool_name: str,
        args: List[str],
        error: str,
    ) -> List[str]:
        """
        エラーに基づいて修正されたパラメータを提案
        
        Args:
            tool_name: ツール名
            args: 元の引数
            error: エラーメッセージ
        
        Returns:
            修正された引数
        """
        modified = args.copy()
        
        # エラーメッセージから修正ヒントを抽出
        error_lower = error.lower()
        
        if 'timeout' in error_lower:
            # タイムアウト → より簡潔な入力に修正
            if len(modified) > 0 and isinstance(modified[0], str):
                modified[0] = modified[0][:50]  # 最初の引数を短縮
        
        elif 'permission' in error_lower or 'denied' in error_lower:
            # パーミッション → より安全なパラメータに修正
            pass  # 実装は環境に応じて
        
        elif 'memory' in error_lower or 'limit' in error_lower:
            # メモリ制限 → より小さいサイズに修正
            if len(modified) > 0:
                modified = modified[:1]  # 最初のパラメータのみ
        
        elif 'format' in error_lower or 'parse' in error_lower:
            # フォーマットエラー → より標準的な形式に修正
            if len(modified) > 0:
                modified[0] = str(modified[0]).strip()
        
        return modified
    
    def _suggest_alternative_tools(
        self,
        tool_name: str,
        context: Dict[str, Any],
    ) -> List[str]:
        """代替ツールを提案"""
        tool_alternatives = {
            'file_create': ['database_write', 'api_call'],
            'file_modify': ['database_update', 'api_call'],
            'file_delete': ['database_delete', 'archive_instead'],
            'web_search': ['database_query', 'api_call'],
            'database_query': ['file_search', 'api_call'],
            'api_call': ['web_search', 'database_query'],
        }
        
        return tool_alternatives.get(tool_name, [])
    
    def _degrade_args(self, args: List[str]) -> List[str]:
        """品質を落とした簡易版の引数を生成"""
        if not args:
            return args
        
        degraded = args[:1]  # 最初の引数のみ使用
        return degraded
    
    def get_fallback_statistics(self) -> Dict[str, Any]:
        """フォールバック統計を取得"""
        if not self.fallback_history:
            return {'total_attempts': 0}
        
        successful = len([a for a in self.fallback_history if a.success])
        
        strategy_counts = {}
        for attempt in self.fallback_history:
            strategy = attempt.strategy.value
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
        
        return {
            'total_attempts': len(self.fallback_history),
            'successful': successful,
            'success_rate': successful / len(self.fallback_history) if self.fallback_history else 0,
            'by_strategy': strategy_counts,
        }
    
    def get_fallback_report(self, error_message: str) -> Dict[str, Any]:
        """エラーに対するフォールバックレポートを生成"""
        
        # このエラーに関連した試行を検索
        related_attempts = [
            a for a in self.fallback_history
            if error_message.lower() in a.original_error.lower()
        ]
        
        successful_strategies = [
            a.strategy.value for a in related_attempts if a.success
        ]
        
        return {
            'error_message': error_message,
            'total_attempts': len(related_attempts),
            'successful_strategies': successful_strategies,
            'recommended_strategy': (
                successful_strategies[0] if successful_strategies
                else 'unknown'
            ),
        }
    
    def clear_history(self):
        """フォールバック履歴をクリア"""
        self.fallback_history = []
        logger.info("Fallback history cleared")
