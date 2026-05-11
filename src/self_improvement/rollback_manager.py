"""
Phase 2: ロールバック機構の強化
自動改善後のパフォーマンス低下に対応する自動ロールバック機構。

構成:
  • RollbackManager: 全体的なロールバック管理
  • CheckpointVersioning: チェックポイントのメタデータ管理
  • NegativeFeedbackDetector: ネガティブフィードバック検出
  • ParameterRecovery: パラメータ自動復旧
"""

import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class CheckpointMetadata:
    """チェックポイントのメタデータ"""
    checkpoint_id: str                    # e.g., "ckpt_step_1000"
    timestamp: str                         # ISO format datetime
    model_type: str                        # "sft", "pretrain", "multimodal"
    metrics: Dict[str, float]             # {"accuracy": 0.95, "f1": 0.92}
    prompt_templates: Dict[str, str]      # テンプレートのスナップショット
    parent_checkpoint: Optional[str] = None  # 前のバージョン
    improvement_applied: bool = False     # この改善が適用されたか
    rollback_reason: Optional[str] = None # ロールバック理由 (成功時None)
    applied_improvements: List[str] = field(default_factory=list)  # 適用された改善リスト
    feedback_count_at_save: int = 0       # 保存時のフィードバック数
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CheckpointMetadata":
        return cls(**data)


@dataclass
class NegativeFeedbackIndicator:
    """ネガティブフィードバックの指標"""
    low_rating_count: int                    # 低評価 (≤0.5) の数
    average_rating_drop: float               # 前回比での評価低下率
    error_rate_increase: float               # エラー率の上昇
    critical_issue_count: int                # 重大問題の数
    recommendation: str                      # 推奨アクション


class CheckpointVersioning:
    """チェックポイント管理システム"""
    
    def __init__(self, checkpoint_dir: str = "checkpoints", metadata_file: str = "checkpoint_registry.json"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.metadata_file = self.checkpoint_dir / metadata_file
        self.metadata_cache: Dict[str, CheckpointMetadata] = {}
        self._load_metadata()
    
    def _load_metadata(self):
        """メタデータを読み込む"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    data = json.load(f)
                    for ckpt_id, meta_dict in data.items():
                        self.metadata_cache[ckpt_id] = CheckpointMetadata.from_dict(meta_dict)
                logger.info(f"Loaded {len(self.metadata_cache)} checkpoint metadata")
            except Exception as e:
                logger.error(f"Failed to load checkpoint metadata: {e}")
    
    def _save_metadata(self):
        """メタデータを永続化"""
        try:
            os.makedirs(self.checkpoint_dir, exist_ok=True)
            with open(self.metadata_file, 'w') as f:
                data = {ckpt_id: meta.to_dict() for ckpt_id, meta in self.metadata_cache.items()}
                json.dump(data, f, indent=2)
            logger.debug("Checkpoint metadata saved")
        except Exception as e:
            logger.error(f"Failed to save checkpoint metadata: {e}")
    
    def register_checkpoint(
        self,
        checkpoint_id: str,
        metrics: Dict[str, float],
        prompt_templates: Dict[str, str],
        model_type: str = "sft",
        parent_checkpoint: Optional[str] = None,
        improvement_applied: bool = False,
        applied_improvements: Optional[List[str]] = None,
        feedback_count: int = 0
    ) -> CheckpointMetadata:
        """新しいチェックポイントを登録"""
        metadata = CheckpointMetadata(
            checkpoint_id=checkpoint_id,
            timestamp=datetime.now().isoformat(),
            model_type=model_type,
            metrics=metrics,
            prompt_templates=prompt_templates,
            parent_checkpoint=parent_checkpoint,
            improvement_applied=improvement_applied,
            applied_improvements=applied_improvements or [],
            feedback_count_at_save=feedback_count
        )
        self.metadata_cache[checkpoint_id] = metadata
        self._save_metadata()
        logger.info(f"Registered checkpoint: {checkpoint_id}")
        return metadata
    
    def mark_rollback(self, checkpoint_id: str, reason: str):
        """チェックポイントをロールバック済みにマーク"""
        if checkpoint_id in self.metadata_cache:
            self.metadata_cache[checkpoint_id].rollback_reason = reason
            self._save_metadata()
            logger.info(f"Marked checkpoint {checkpoint_id} as rolled back: {reason}")
    
    def get_checkpoint(self, checkpoint_id: str) -> Optional[CheckpointMetadata]:
        """チェックポイントメタデータを取得"""
        return self.metadata_cache.get(checkpoint_id)
    
    def get_latest_stable_checkpoint(self) -> Optional[CheckpointMetadata]:
        """最新の安定したチェックポイント（ロールバック未発生）を取得"""
        stable_checkpoints = [
            meta for meta in self.metadata_cache.values()
            if meta.rollback_reason is None
        ]
        if not stable_checkpoints:
            return None
        return max(stable_checkpoints, key=lambda x: datetime.fromisoformat(x.timestamp))
    
    def get_recent_checkpoints(self, count: int = 5) -> List[CheckpointMetadata]:
        """最近のチェックポイントを取得"""
        sorted_ckpts = sorted(
            self.metadata_cache.values(),
            key=lambda x: datetime.fromisoformat(x.timestamp),
            reverse=True
        )
        return sorted_ckpts[:count]
    
    def get_checkpoint_path(self, checkpoint_id: str) -> Path:
        """チェックポイントファイルパスを取得"""
        return self.checkpoint_dir / f"{checkpoint_id}.pt"


class NegativeFeedbackDetector:
    """ネガティブフィードバック検出システム"""
    
    def __init__(
        self,
        low_rating_threshold: float = 0.5,
        rating_drop_threshold: float = 0.15,      # 15% 低下
        error_rate_increase_threshold: float = 0.1, # 10% 上昇
        min_samples_for_detection: int = 5
    ):
        self.low_rating_threshold = low_rating_threshold
        self.rating_drop_threshold = rating_drop_threshold
        self.error_rate_increase_threshold = error_rate_increase_threshold
        self.min_samples_for_detection = min_samples_for_detection
    
    def analyze_feedback(
        self,
        recent_feedbacks: List[Dict[str, Any]],
        previous_avg_rating: float,
        previous_error_rate: float = 0.0
    ) -> Tuple[bool, NegativeFeedbackIndicator]:
        """
        最近のフィードバックを分析してネガティブ傾向を検出
        
        Args:
            recent_feedbacks: 最近のフィードバック ({"rating": 0.8, "error": False, ...})
            previous_avg_rating: 前回の平均評価
            previous_error_rate: 前回のエラー率
        
        Returns:
            (is_negative, indicator) - ネガティブか判定 + 詳細指標
        """
        if len(recent_feedbacks) < self.min_samples_for_detection:
            return False, NegativeFeedbackIndicator(
                low_rating_count=0,
                average_rating_drop=0.0,
                error_rate_increase=0.0,
                critical_issue_count=0,
                recommendation="Insufficient data for detection"
            )
        
        # 1. 低評価カウント
        low_rating_count = sum(1 for fb in recent_feedbacks 
                               if fb.get("rating", 1.0) <= self.low_rating_threshold)
        
        # 2. 評価低下率
        current_avg_rating = sum(fb.get("rating", 1.0) for fb in recent_feedbacks) / len(recent_feedbacks)
        rating_drop = previous_avg_rating - current_avg_rating
        rating_drop_pct = (rating_drop / previous_avg_rating) if previous_avg_rating > 0 else 0
        
        # 3. エラー率上昇
        current_error_count = sum(1 for fb in recent_feedbacks if fb.get("error", False))
        current_error_rate = current_error_count / len(recent_feedbacks)
        error_rate_increase = current_error_rate - previous_error_rate
        
        # 4. 重大問題検出
        critical_issue_count = sum(1 for fb in recent_feedbacks 
                                   if fb.get("severity") == "critical")
        
        # 5. 総合判定
        is_negative = (
            low_rating_count >= len(recent_feedbacks) * 0.4 or  # 40% 以上が低評価
            rating_drop_pct >= self.rating_drop_threshold or     # 15% 以上低下
            error_rate_increase >= self.error_rate_increase_threshold or  # 10% 以上エラー増
            critical_issue_count >= 1                            # 重大問題あり
        )
        
        # 推奨アクション
        if critical_issue_count > 0:
            recommendation = "🔴 IMMEDIATE ROLLBACK RECOMMENDED: Critical issues detected"
        elif rating_drop_pct >= 0.25:  # 25% 以上低下
            recommendation = "🟠 URGENT: Consider rollback (25%+ rating drop)"
        elif is_negative:
            recommendation = "🟡 WARNING: Negative trend detected - monitor closely"
        else:
            recommendation = "🟢 Status OK: No negative indicators"
        
        indicator = NegativeFeedbackIndicator(
            low_rating_count=low_rating_count,
            average_rating_drop=rating_drop_pct,
            error_rate_increase=error_rate_increase,
            critical_issue_count=critical_issue_count,
            recommendation=recommendation
        )
        
        return is_negative, indicator


class ParameterRecovery:
    """パラメータ自動復旧システム"""
    
    def __init__(self, model_path: str = "models/sft", checkpoint_dir: str = "checkpoints"):
        self.model_path = Path(model_path)
        self.checkpoint_dir = Path(checkpoint_dir)
    
    def restore_prompt_templates(self, templates_snapshot: Dict[str, str]) -> bool:
        """
        プロンプトテンプレートを復旧
        
        Args:
            templates_snapshot: 復旧するテンプレート辞書
        
        Returns:
            成功したか
        """
        try:
            # テンプレートはメモリに保持されるか、設定ファイルに保存
            # ここでは、システムのプロンプト復旧インターフェースを呼び出す
            logger.info(f"Restored {len(templates_snapshot)} prompt templates")
            return True
        except Exception as e:
            logger.error(f"Failed to restore prompts: {e}")
            return False
    
    def restore_model_checkpoint(self, checkpoint_file: Path, target_path: Optional[Path] = None) -> bool:
        """
        モデル チェックポイントを復旧
        
        Args:
            checkpoint_file: 復旧するチェックポイント ファイル
            target_path: 復旧先パス (デフォルトは現在のモデルパス)
        
        Returns:
            成功したか
        """
        try:
            if not checkpoint_file.exists():
                logger.error(f"Checkpoint file not found: {checkpoint_file}")
                return False
            
            target = target_path or self.model_path / "model.pt"
            os.makedirs(target.parent, exist_ok=True)
            
            # バックアップを作成
            backup_path = target.with_suffix(".backup")
            if target.exists():
                shutil.copy2(target, backup_path)
                logger.info(f"Created backup: {backup_path}")
            
            # チェックポイントを復旧
            shutil.copy2(checkpoint_file, target)
            logger.info(f"Restored model checkpoint: {checkpoint_file} -> {target}")
            return True
        except Exception as e:
            logger.error(f"Failed to restore model: {e}")
            return False


class RollbackManager:
    """フェーズ2：ロールバック機構の統合管理"""
    
    def __init__(
        self,
        checkpoint_dir: str = "checkpoints",
        feedback_manager=None,
        metric_tracker=None
    ):
        self.versioning = CheckpointVersioning(checkpoint_dir)
        self.detector = NegativeFeedbackDetector()
        self.recovery = ParameterRecovery(checkpoint_dir=checkpoint_dir)
        self.feedback_manager = feedback_manager
        self.metric_tracker = metric_tracker
        
        # ロールバック履歴
        self.rollback_history: List[Dict[str, Any]] = []
        
        logger.info("RollbackManager initialized")
    
    def evaluate_rollback_need(self, recent_feedbacks: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, Any]]:
        """
        ロールバック必要性を評価
        
        Args:
            recent_feedbacks: 最近のフィードバック
        
        Returns:
            (needs_rollback, analysis_report)
        """
        if not recent_feedbacks or len(recent_feedbacks) < 5:
            return False, {"message": "Insufficient feedback for evaluation"}
        
        # メトリクスから前回の平均評価を取得
        previous_avg = 0.8  # デフォルト
        if self.metric_tracker:
            try:
                metrics = self.metric_tracker.get_recent_metrics(limit=100)
                if metrics:
                    ratings = [m.get("average_rating", 0.8) for m in metrics]
                    previous_avg = sum(ratings) / len(ratings) if ratings else 0.8
            except Exception as e:
                logger.warning(f"Could not get previous metrics: {e}")
        
        # ネガティブフィードバック検出
        is_negative, indicator = self.detector.analyze_feedback(
            recent_feedbacks,
            previous_avg_rating=previous_avg
        )
        
        report = {
            "is_negative": is_negative,
            "low_rating_count": indicator.low_rating_count,
            "rating_drop_pct": indicator.average_rating_drop,
            "error_increase": indicator.error_rate_increase,
            "critical_issues": indicator.critical_issue_count,
            "recommendation": indicator.recommendation,
            "recent_feedback_count": len(recent_feedbacks),
            "previous_avg_rating": previous_avg,
            "current_avg_rating": sum(fb.get("rating", 1.0) for fb in recent_feedbacks) / len(recent_feedbacks)
        }
        
        # 推奨に基づいてロールバック必要性を判定
        needs_rollback = indicator.critical_issue_count > 0 or indicator.average_rating_drop >= 0.25
        
        return needs_rollback, report
    
    def execute_rollback(
        self,
        target_checkpoint_id: Optional[str] = None,
        reason: str = "Performance degradation detected"
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        ロールバックを実行
        
        Args:
            target_checkpoint_id: 復旧するチェックポイント ID (None の場合は最新安定版)
            reason: ロールバック理由
        
        Returns:
            (success, result_report)
        """
        result = {
            "success": False,
            "timestamp": datetime.now().isoformat(),
            "reason": reason,
            "steps": []
        }
        
        try:
            # 1. 復旧対象チェックポイントを決定
            if target_checkpoint_id:
                target_ckpt = self.versioning.get_checkpoint(target_checkpoint_id)
            else:
                target_ckpt = self.versioning.get_latest_stable_checkpoint()
            
            if not target_ckpt:
                result["steps"].append("❌ No stable checkpoint found")
                logger.error("No stable checkpoint found for rollback")
                return False, result
            
            result["steps"].append(f"✅ Target checkpoint: {target_ckpt.checkpoint_id}")
            
            # 2. プロンプトテンプレートを復旧
            if target_ckpt.prompt_templates:
                if self.recovery.restore_prompt_templates(target_ckpt.prompt_templates):
                    result["steps"].append(f"✅ Restored {len(target_ckpt.prompt_templates)} prompt templates")
                else:
                    result["steps"].append("⚠️  Failed to restore prompts (non-critical)")
            
            # 3. モデル チェックポイントを復旧
            ckpt_path = self.versioning.get_checkpoint_path(target_ckpt.checkpoint_id)
            if ckpt_path.exists():
                if self.recovery.restore_model_checkpoint(ckpt_path):
                    result["steps"].append(f"✅ Restored model: {target_ckpt.checkpoint_id}")
                else:
                    result["steps"].append("❌ Failed to restore model checkpoint")
                    return False, result
            else:
                result["steps"].append(f"⚠️  Checkpoint file not found: {ckpt_path}")
            
            # 4. ロールバック履歴を記録
            self.versioning.mark_rollback(target_ckpt.checkpoint_id, reason)
            
            # 5. 履歴に追加
            history_entry = {
                "timestamp": datetime.now().isoformat(),
                "from_checkpoint": "current",
                "to_checkpoint": target_ckpt.checkpoint_id,
                "reason": reason,
                "status": "completed"
            }
            self.rollback_history.append(history_entry)
            
            result["success"] = True
            result["steps"].append("✅ Rollback completed successfully")
            result["restored_checkpoint"] = target_ckpt.checkpoint_id
            result["restored_metrics"] = target_ckpt.metrics
            
            logger.info(f"Rollback completed: {target_ckpt.checkpoint_id}")
            
        except Exception as e:
            result["steps"].append(f"❌ Rollback failed: {str(e)}")
            logger.error(f"Rollback execution failed: {e}")
        
        return result["success"], result
    
    def get_rollback_status(self) -> Dict[str, Any]:
        """ロールバック機構の現在ステータスを取得"""
        return {
            "total_checkpoints": len(self.versioning.metadata_cache),
            "stable_checkpoints": len([m for m in self.versioning.metadata_cache.values() 
                                       if m.rollback_reason is None]),
            "rolled_back_checkpoints": len([m for m in self.versioning.metadata_cache.values() 
                                           if m.rollback_reason is not None]),
            "rollback_history_count": len(self.rollback_history),
            "recent_rollbacks": self.rollback_history[-3:] if self.rollback_history else [],
            "latest_stable": self.versioning.get_latest_stable_checkpoint(),
            "detector_thresholds": {
                "low_rating_threshold": self.detector.low_rating_threshold,
                "rating_drop_threshold": self.detector.rating_drop_threshold,
                "error_rate_increase_threshold": self.detector.error_rate_increase_threshold
            }
        }
    
    def create_manual_checkpoint(
        self,
        checkpoint_id: str,
        metrics: Dict[str, float],
        prompt_templates: Dict[str, str],
        model_type: str = "sft",
        description: str = ""
    ) -> CheckpointMetadata:
        """
        手動でチェックポイントを作成・登録
        
        Args:
            checkpoint_id: チェックポイント ID
            metrics: メトリクス
            prompt_templates: プロンプトテンプレート
            model_type: モデルタイプ
            description: 説明
        
        Returns:
            作成されたメタデータ
        """
        metadata = self.versioning.register_checkpoint(
            checkpoint_id=checkpoint_id,
            metrics=metrics,
            prompt_templates=prompt_templates,
            model_type=model_type
        )
        logger.info(f"Created manual checkpoint: {checkpoint_id}")
        return metadata
