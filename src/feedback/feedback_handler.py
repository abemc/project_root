"""
Feedback Handler: ユーザーフィードバック管理・計画への適用

ユーザーからの修正指示・提案を記録し、
次回のタスク計画で自動的に適用する学習メカニズム。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    """フィードバック種別"""
    TOOL_CORRECTION = "tool_correction"  # 「このツールは間違っていた」
    PARAMETER_ADJUSTMENT = "parameter_adjustment"  # 「パラメータを変更すべき」
    STRATEGY_CHANGE = "strategy_change"  # 「戦略全体を変更すべき」
    ACCURACY_IMPROVEMENT = "accuracy_improvement"  # 「精度向上のコツ」
    PERFORMANCE_ISSUE = "performance_issue"  # 「速度が遅すぎる」
    SAFETY_CONCERN = "safety_concern"  # 「安全性上の懸念」
    OTHER = "other"


class FeedbackSeverity(Enum):
    """フィードバックの重要度"""
    LOW = 0.3
    MEDIUM = 0.6
    HIGH = 0.9
    CRITICAL = 1.0


@dataclass
class Feedback:
    """フィードバック記録"""
    feedback_id: str
    task_id: str
    feedback_type: FeedbackType
    severity: FeedbackSeverity
    content: str  # ユーザーの修正指示テキスト
    affected_component: str  # "tool:web_search", "parameter:max_retries" など
    suggested_action: Optional[str] = None  # 推奨アクション
    user_id: Optional[str] = None  # ユーザー識別子
    timestamp: datetime = field(default_factory=datetime.now)
    applied: bool = False  # 計画に適用済みかどうか
    applied_timestamp: Optional[datetime] = None


@dataclass
class FeedbackPattern:
    """フィードバックパターン（複数フィードバックから学習）"""
    pattern_id: str
    component: str  # 対象コンポーネント
    pattern_type: FeedbackType
    frequency: int  # このパターンの出現回数
    suggestions: List[str]  # 推奨アクション一覧
    confidence: float  # 信頼度 (0-1)
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)


class FeedbackHandler:
    """フィードバック記録・適用管理"""
    
    def __init__(
        self,
        storage_dir: str = "logs",
        auto_apply: bool = True,
        pattern_threshold: int = 3,  # このフィードバック数でパターン生成
    ):
        """
        初期化
        
        Args:
            storage_dir: フィードバック保存ディレクトリ
            auto_apply: 計画時に自動適用するか
            pattern_threshold: パターン生成の閾値フィードバック数
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.feedback_file = self.storage_dir / "feedbacks.jsonl"
        self.patterns_file = self.storage_dir / "feedback_patterns.json"
        
        self.auto_apply = auto_apply
        self.pattern_threshold = pattern_threshold
        
        self.feedbacks: List[Feedback] = []
        self.patterns: Dict[str, FeedbackPattern] = {}
        
        self._load_feedbacks()
        self._load_patterns()
    
    def _load_feedbacks(self):
        """フィードバック履歴をロード"""
        if not self.feedback_file.exists():
            return
        
        try:
            with open(self.feedback_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        fb = Feedback(
                            feedback_id=data['feedback_id'],
                            task_id=data['task_id'],
                            feedback_type=FeedbackType(data['feedback_type']),
                            severity=FeedbackSeverity[data['severity'].upper()],
                            content=data['content'],
                            affected_component=data['affected_component'],
                            suggested_action=data.get('suggested_action'),
                            user_id=data.get('user_id'),
                            timestamp=datetime.fromisoformat(data['timestamp']),
                            applied=data.get('applied', False),
                        )
                        self.feedbacks.append(fb)
        except Exception as e:
            logger.warning(f"Failed to load feedbacks: {e}")
    
    def _load_patterns(self):
        """フィードバックパターンをロード"""
        if not self.patterns_file.exists():
            return
        
        try:
            with open(self.patterns_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for pid, pdata in data.items():
                    pattern = FeedbackPattern(
                        pattern_id=pdata['pattern_id'],
                        component=pdata['component'],
                        pattern_type=FeedbackType(pdata['pattern_type']),
                        frequency=pdata['frequency'],
                        suggestions=pdata['suggestions'],
                        confidence=pdata['confidence'],
                        created_at=datetime.fromisoformat(pdata['created_at']),
                        last_updated=datetime.fromisoformat(pdata['last_updated']),
                    )
                    self.patterns[pid] = pattern
        except Exception as e:
            logger.warning(f"Failed to load patterns: {e}")
    
    def record_feedback(
        self,
        task_id: str,
        feedback_type: FeedbackType,
        severity: FeedbackSeverity,
        content: str,
        affected_component: str,
        suggested_action: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """
        ユーザーフィードバックを記録
        
        Args:
            task_id: 対象タスク ID
            feedback_type: フィードバック種別
            severity: 重要度
            content: フィードバック本文
            affected_component: 影響を受けるコンポーネント
            suggested_action: ユーザーの推奨アクション
            user_id: ユーザー ID
        
        Returns:
            feedback_id
        """
        feedback = Feedback(
            feedback_id=f"{task_id}_{datetime.now().timestamp()}",
            task_id=task_id,
            feedback_type=feedback_type,
            severity=severity,
            content=content,
            affected_component=affected_component,
            suggested_action=suggested_action,
            user_id=user_id,
        )
        
        self.feedbacks.append(feedback)
        
        # ファイルに保存
        try:
            with open(self.feedback_file, 'a', encoding='utf-8') as f:
                entry = {
                    'feedback_id': feedback.feedback_id,
                    'task_id': feedback.task_id,
                    'feedback_type': feedback.feedback_type.value,
                    'severity': feedback.severity.name,
                    'content': feedback.content,
                    'affected_component': feedback.affected_component,
                    'suggested_action': feedback.suggested_action,
                    'user_id': feedback.user_id,
                    'timestamp': feedback.timestamp.isoformat(),
                    'applied': feedback.applied,
                }
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"Failed to save feedback: {e}")
        
        # パターン検出
        self._update_patterns()
        
        logger.info(f"Feedback recorded: {feedback.feedback_id} ({feedback_type.value})")
        return feedback.feedback_id
    
    def _update_patterns(self):
        """フィードバックからパターンを抽出・更新"""
        # コンポーネント & 種別 でグループ化
        pattern_groups: Dict[tuple, List[Feedback]] = {}
        
        for fb in self.feedbacks:
            key = (fb.affected_component, fb.feedback_type.value)
            if key not in pattern_groups:
                pattern_groups[key] = []
            pattern_groups[key].append(fb)
        
        # 閾値を超えたものをパターン化
        for (component, fb_type), fbs in pattern_groups.items():
            if len(fbs) >= self.pattern_threshold:
                pattern_id = f"{component}_{fb_type}"
                
                # 新しいパターンまたは既存パターンの更新
                suggestions = list(set([
                    fb.suggested_action
                    for fb in fbs
                    if fb.suggested_action
                ]))
                
                avg_severity = sum(fb.severity.value for fb in fbs) / len(fbs)
                confidence = min(1.0, len(fbs) / (self.pattern_threshold * 2))
                
                if pattern_id in self.patterns:
                    # 既存パターン更新
                    pattern = self.patterns[pattern_id]
                    pattern.frequency = len(fbs)
                    pattern.suggestions = suggestions
                    pattern.confidence = confidence
                    pattern.last_updated = datetime.now()
                else:
                    # 新規パターン作成
                    pattern = FeedbackPattern(
                        pattern_id=pattern_id,
                        component=component,
                        pattern_type=FeedbackType(fb_type),
                        frequency=len(fbs),
                        suggestions=suggestions,
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
                    'component': p.component,
                    'pattern_type': p.pattern_type.value,
                    'frequency': p.frequency,
                    'suggestions': p.suggestions,
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
    
    def apply_feedback_to_plan(
        self,
        execution_plan: Dict[str, Any],
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        計画にフィードバックを適用
        
        Args:
            execution_plan: ExecutionPlan 形式（辞書）
            task_id: 特定タスクのフィードバックのみ適用（None=全て）
        
        Returns:
            修正された execution_plan
        """
        modified_plan = execution_plan.copy()
        
        # 適用対象フィードバックを抽出
        applicable_feedbacks = []
        for fb in self.feedbacks:
            if fb.applied:
                continue
            if task_id and fb.task_id != task_id:
                continue
            if not self.auto_apply and fb.severity.value < FeedbackSeverity.HIGH.value:
                continue
            applicable_feedbacks.append(fb)
        
        if not applicable_feedbacks:
            logger.debug("No applicable feedbacks found")
            return modified_plan
        
        # フィードバックの種別ごとに適用ロジック
        for fb in applicable_feedbacks:
            if fb.feedback_type == FeedbackType.TOOL_CORRECTION:
                # ツール選択を修正
                modified_plan = self._apply_tool_correction(modified_plan, fb)
            
            elif fb.feedback_type == FeedbackType.PARAMETER_ADJUSTMENT:
                # パラメータを調整
                modified_plan = self._apply_parameter_adjustment(modified_plan, fb)
            
            elif fb.feedback_type == FeedbackType.STRATEGY_CHANGE:
                # タスク分解戦略を変更
                modified_plan = self._apply_strategy_change(modified_plan, fb)
            
            # 適用マーク
            fb.applied = True
            fb.applied_timestamp = datetime.now()
        
        # 修正したフィードバック履歴をセーブ
        self._save_feedbacks()
        
        return modified_plan
    
    def _apply_tool_correction(self, plan: Dict[str, Any], fb: Feedback) -> Dict[str, Any]:
        """ツール修正を適用"""
        logger.info(f"Applying tool correction: {fb.affected_component}")
        
        # 簡易実装: 提案されたアクションを plan に記録
        if 'feedback_applied' not in plan:
            plan['feedback_applied'] = []
        
        plan['feedback_applied'].append({
            'type': 'tool_correction',
            'component': fb.affected_component,
            'suggestion': fb.suggested_action,
            'reason': fb.content,
        })
        
        return plan
    
    def _apply_parameter_adjustment(self, plan: Dict[str, Any], fb: Feedback) -> Dict[str, Any]:
        """パラメータ調整を適用"""
        logger.info(f"Applying parameter adjustment: {fb.affected_component}")
        
        if 'feedback_applied' not in plan:
            plan['feedback_applied'] = []
        
        plan['feedback_applied'].append({
            'type': 'parameter_adjustment',
            'component': fb.affected_component,
            'suggestion': fb.suggested_action,
            'reason': fb.content,
        })
        
        return plan
    
    def _apply_strategy_change(self, plan: Dict[str, Any], fb: Feedback) -> Dict[str, Any]:
        """戦略変更を適用"""
        logger.info(f"Applying strategy change based on feedback: {fb.affected_component}")
        
        if 'feedback_applied' not in plan:
            plan['feedback_applied'] = []
        
        plan['feedback_applied'].append({
            'type': 'strategy_change',
            'component': fb.affected_component,
            'suggestion': fb.suggested_action,
            'reason': fb.content,
        })
        
        return plan
    
    def _save_feedbacks(self):
        """フィードバック履歴を再保存"""
        try:
            with open(self.feedback_file, 'w', encoding='utf-8') as f:
                for fb in self.feedbacks:
                    entry = {
                        'feedback_id': fb.feedback_id,
                        'task_id': fb.task_id,
                        'feedback_type': fb.feedback_type.value,
                        'severity': fb.severity.name,
                        'content': fb.content,
                        'affected_component': fb.affected_component,
                        'suggested_action': fb.suggested_action,
                        'user_id': fb.user_id,
                        'timestamp': fb.timestamp.isoformat(),
                        'applied': fb.applied,
                        'applied_timestamp': fb.applied_timestamp.isoformat() if fb.applied_timestamp else None,
                    }
                    f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"Failed to save feedbacks: {e}")
    
    def get_feedbacks_for_component(
        self,
        component: str,
        unapplied_only: bool = False,
    ) -> List[Feedback]:
        """特定コンポーネントのフィードバックを取得"""
        feedbacks = [
            fb for fb in self.feedbacks
            if fb.affected_component == component
        ]
        
        if unapplied_only:
            feedbacks = [fb for fb in feedbacks if not fb.applied]
        
        return feedbacks
    
    def get_patterns_for_component(self, component: str) -> List[FeedbackPattern]:
        """特定コンポーネントのパターンを取得"""
        return [
            p for p in self.patterns.values()
            if p.component == component
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """フィードバック統計を取得"""
        applied_count = sum(1 for fb in self.feedbacks if fb.applied)
        unapplied_count = len(self.feedbacks) - applied_count
        
        type_counts = {}
        for fb in self.feedbacks:
            key = fb.feedback_type.value
            type_counts[key] = type_counts.get(key, 0) + 1
        
        severity_scores = {}
        for fb in self.feedbacks:
            key = fb.severity.name
            severity_scores[key] = severity_scores.get(key, 0) + fb.severity.value
        
        return {
            'total_feedbacks': len(self.feedbacks),
            'applied': applied_count,
            'unapplied': unapplied_count,
            'patterns_discovered': len(self.patterns),
            'feedbacks_by_type': type_counts,
            'severity_distribution': severity_scores,
        }
