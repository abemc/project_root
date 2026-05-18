"""
Error Learning: 失敗パターン学習・自動回復

エラーが発生した際、類似の過去エラーから解決方法を検索・学習。
次回同じシチュエーションなら自動的に改善したアクションを提案。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json
import logging
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """エラー分類"""
    TOOL_FAILURE = "tool_failure"  # ツール実行失敗
    TIMEOUT = "timeout"  # タイムアウト
    INVALID_PARAMETER = "invalid_parameter"  # パラメータエラー
    RESOURCE_EXHAUSTED = "resource_exhausted"  # リソース不足
    EXTERNAL_SERVICE = "external_service"  # 外部サービスエラー
    LOGIC_ERROR = "logic_error"  # 論理エラー
    PERMISSION_DENIED = "permission_denied"  # 権限エラー
    UNKNOWN = "unknown"


@dataclass
class ErrorRecord:
    """エラー記録"""
    error_id: str
    task_id: str
    tool_name: str
    error_category: ErrorCategory
    error_message: str
    context: Dict[str, Any]  # エラー発生時のコンテキスト
    timestamp: datetime = field(default_factory=datetime.now)
    resolution: Optional[str] = None  # 解決方法
    resolution_timestamp: Optional[datetime] = None
    resolved: bool = False


@dataclass
class ErrorPattern:
    """エラーパターン（複数エラーから学習）"""
    pattern_id: str
    error_category: ErrorCategory
    tool_name: str
    error_signature: str  # エラーメッセージのハッシュ値
    frequency: int  # 出現回数
    resolutions: List[str]  # 推奨解決方法
    confidence: float  # 信頼度 (0-1)
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)


class ErrorLearner:
    """エラー学習・自動回復管理"""
    
    def __init__(
        self,
        storage_dir: str = "logs",
        pattern_threshold: int = 3,  # このエラー数でパターン認定
        retention_days: int = 90,  # エラー保持日数
    ):
        """
        初期化
        
        Args:
            storage_dir: エラーログ保存ディレクトリ
            pattern_threshold: パターン認定の閾値
            retention_days: エラー履歴の保持期間
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.errors_file = self.storage_dir / "errors.jsonl"
        self.patterns_file = self.storage_dir / "error_patterns.json"
        
        self.pattern_threshold = pattern_threshold
        self.retention_days = retention_days
        
        self.errors: List[ErrorRecord] = []
        self.patterns: Dict[str, ErrorPattern] = {}
        
        self._load_errors()
        self._load_patterns()
    
    def _load_errors(self):
        """エラー履歴をロード"""
        if not self.errors_file.exists():
            return
        
        try:
            with open(self.errors_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        error = ErrorRecord(
                            error_id=data['error_id'],
                            task_id=data['task_id'],
                            tool_name=data['tool_name'],
                            error_category=ErrorCategory(data['error_category']),
                            error_message=data['error_message'],
                            context=data['context'],
                            timestamp=datetime.fromisoformat(data['timestamp']),
                            resolution=data.get('resolution'),
                            resolution_timestamp=(
                                datetime.fromisoformat(data['resolution_timestamp'])
                                if data.get('resolution_timestamp')
                                else None
                            ),
                            resolved=data.get('resolved', False),
                        )
                        self.errors.append(error)
        except Exception as e:
            logger.warning(f"Failed to load errors: {e}")
    
    def _load_patterns(self):
        """エラーパターンをロード"""
        if not self.patterns_file.exists():
            return
        
        try:
            with open(self.patterns_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for pid, pdata in data.items():
                    pattern = ErrorPattern(
                        pattern_id=pdata['pattern_id'],
                        error_category=ErrorCategory(pdata['error_category']),
                        tool_name=pdata['tool_name'],
                        error_signature=pdata['error_signature'],
                        frequency=pdata['frequency'],
                        resolutions=pdata['resolutions'],
                        confidence=pdata['confidence'],
                        created_at=datetime.fromisoformat(pdata['created_at']),
                        last_updated=datetime.fromisoformat(pdata['last_updated']),
                    )
                    self.patterns[pid] = pattern
        except Exception as e:
            logger.warning(f"Failed to load patterns: {e}")
    
    def record_error(
        self,
        task_id: str,
        tool_name: str,
        error_category: ErrorCategory,
        error_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        エラーを記録
        
        Args:
            task_id: タスク ID
            tool_name: 失敗したツール名
            error_category: エラー分類
            error_message: エラーメッセージ
            context: エラー発生時のコンテキスト
        
        Returns:
            error_id
        """
        error = ErrorRecord(
            error_id=f"{tool_name}_{datetime.now().timestamp()}",
            task_id=task_id,
            tool_name=tool_name,
            error_category=error_category,
            error_message=error_message,
            context=context or {},
        )
        
        self.errors.append(error)
        
        # ファイルに保存
        try:
            with open(self.errors_file, 'a', encoding='utf-8') as f:
                entry = {
                    'error_id': error.error_id,
                    'task_id': error.task_id,
                    'tool_name': error.tool_name,
                    'error_category': error.error_category.value,
                    'error_message': error.error_message,
                    'context': error.context,
                    'timestamp': error.timestamp.isoformat(),
                    'resolution': error.resolution,
                    'resolution_timestamp': (
                        error.resolution_timestamp.isoformat()
                        if error.resolution_timestamp
                        else None
                    ),
                    'resolved': error.resolved,
                }
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"Failed to save error: {e}")
        
        # パターン検出
        self._update_patterns()
        
        logger.info(f"Error recorded: {error.error_id} ({error_category.value})")
        return error.error_id
    
    def resolve_error(
        self,
        error_id: str,
        resolution: str,
    ):
        """
        エラーを解決済みとしてマーク
        
        Args:
            error_id: エラー ID
            resolution: 採取した解決方法
        """
        for error in self.errors:
            if error.error_id == error_id:
                error.resolved = True
                error.resolution = resolution
                error.resolution_timestamp = datetime.now()
                self._save_errors()
                logger.info(f"Error {error_id} marked as resolved")
                return
    
    def _update_patterns(self):
        """エラーからパターンを抽出・更新"""
        # エラー署名 & ツール でグループ化
        pattern_groups: Dict[Tuple[str, str], List[ErrorRecord]] = {}
        
        for err in self.errors:
            # エラーメッセージのハッシュ値でシグネチャ生成
            sig = hashlib.md5(err.error_message.encode()).hexdigest()[:16]
            key = (sig, err.tool_name)
            
            if key not in pattern_groups:
                pattern_groups[key] = []
            pattern_groups[key].append(err)
        
        # 閾値を超えたものをパターン化
        for (sig, tool_name), errors in pattern_groups.items():
            if len(errors) >= self.pattern_threshold:
                pattern_id = f"{tool_name}_{sig}"
                
                # 解決方法を収集
                resolutions = list(set([
                    err.resolution
                    for err in errors
                    if err.resolution and err.resolved
                ]))
                
                resolution_rate = sum(1 for err in errors if err.resolved) / len(errors)
                confidence = min(1.0, resolution_rate * (len(errors) / (self.pattern_threshold * 2)))
                
                # 最初のエラーから category を確定
                category = errors[0].error_category
                
                if pattern_id in self.patterns:
                    # 既存パターン更新
                    pattern = self.patterns[pattern_id]
                    pattern.frequency = len(errors)
                    pattern.resolutions = resolutions
                    pattern.confidence = confidence
                    pattern.last_updated = datetime.now()
                else:
                    # 新規パターン作成
                    pattern = ErrorPattern(
                        pattern_id=pattern_id,
                        error_category=category,
                        tool_name=tool_name,
                        error_signature=sig,
                        frequency=len(errors),
                        resolutions=resolutions,
                        confidence=confidence,
                    )
                    self.patterns[pattern_id] = pattern
        
        self._save_patterns()
    
    def _save_patterns(self):
        """パターンをファイルに保存"""
        try:
            patterns_data = {
                pid: {
                    'pattern_id': p.pattern_id,
                    'error_category': p.error_category.value,
                    'tool_name': p.tool_name,
                    'error_signature': p.error_signature,
                    'frequency': p.frequency,
                    'resolutions': p.resolutions,
                    'confidence': p.confidence,
                    'created_at': p.created_at.isoformat(),
                    'last_updated': p.last_updated.isoformat(),
                }
                for pid, p in self.patterns.items()
            }
            with open(self.patterns_file, 'w', encoding='utf-8') as f:
                json.dump(patterns_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save patterns: {e}")
    
    def _save_errors(self):
        """エラー履歴を再保存"""
        try:
            with open(self.errors_file, 'w', encoding='utf-8') as f:
                for err in self.errors:
                    entry = {
                        'error_id': err.error_id,
                        'task_id': err.task_id,
                        'tool_name': err.tool_name,
                        'error_category': err.error_category.value,
                        'error_message': err.error_message,
                        'context': err.context,
                        'timestamp': err.timestamp.isoformat(),
                        'resolution': err.resolution,
                        'resolution_timestamp': (
                            err.resolution_timestamp.isoformat()
                            if err.resolution_timestamp
                            else None
                        ),
                        'resolved': err.resolved,
                    }
                    f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"Failed to save errors: {e}")
    
    def search_similar_errors(
        self,
        error_message: str,
        tool_name: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Tuple[ErrorRecord, float]]:
        """
        類似エラーを検索（文字列類似度ベース）
        
        Args:
            error_message: 検索対象エラーメッセージ
            tool_name: ツール名（オプション）
            top_k: 取得件数
        
        Returns:
            [(エラー, 類似度), ...] のリスト
        """
        # 簡易実装: 単語の重複数で類似度計算
        query_words = set(error_message.lower().split())
        results = []
        
        for err in self.errors:
            if tool_name and err.tool_name != tool_name:
                continue
            
            err_words = set(err.error_message.lower().split())
            overlap = len(query_words & err_words)
            similarity = overlap / max(len(query_words), len(err_words))
            
            if similarity > 0.3:  # 30% 以上の類似度
                results.append((err, similarity))
        
        # 類似度でソート
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def get_recovery_suggestions(
        self,
        error_message: str,
        tool_name: str,
    ) -> List[str]:
        """
        エラーメッセージから回復提案を取得
        
        Args:
            error_message: エラーメッセージ
            tool_name: ツール名
        
        Returns:
            回復提案リスト
        """
        # パターンから推奨解決方法を取得
        suggestions = []
        
        # 1. シグネチャベースの検索
        sig = hashlib.md5(error_message.encode()).hexdigest()[:16]
        pattern_id = f"{tool_name}_{sig}"
        
        if pattern_id in self.patterns:
            pattern = self.patterns[pattern_id]
            suggestions.extend(pattern.resolutions)
        
        # 2. 類似エラーから学習
        similar = self.search_similar_errors(error_message, tool_name)
        for err, _ in similar:
            if err.resolved and err.resolution:
                suggestions.append(err.resolution)
        
        # 重複を除去
        suggestions = list(set(suggestions))
        
        return suggestions
    
    def cleanup_old_errors(self):
        """古いエラー履歴を削除"""
        now = datetime.now()
        cutoff = now - timedelta(days=self.retention_days)
        
        before_count = len(self.errors)
        self.errors = [err for err in self.errors if err.timestamp > cutoff]
        after_count = len(self.errors)
        
        deleted_count = before_count - after_count
        if deleted_count > 0:
            self._save_errors()
            logger.info(f"Cleaned up {deleted_count} old errors")
    
    def get_stats(self) -> Dict[str, Any]:
        """エラー統計を取得"""
        resolved_count = sum(1 for err in self.errors if err.resolved)
        unresolved_count = len(self.errors) - resolved_count
        
        category_counts = {}
        for err in self.errors:
            key = err.error_category.value
            category_counts[key] = category_counts.get(key, 0) + 1
        
        tool_error_counts = {}
        for err in self.errors:
            key = err.tool_name
            tool_error_counts[key] = tool_error_counts.get(key, 0) + 1
        
        return {
            'total_errors': len(self.errors),
            'resolved': resolved_count,
            'unresolved': unresolved_count,
            'resolution_rate': resolved_count / max(len(self.errors), 1),
            'patterns_discovered': len(self.patterns),
            'errors_by_category': category_counts,
            'errors_by_tool': tool_error_counts,
        }
