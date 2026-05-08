"""フィードバック駆動型トリガーシステム

フィードバックが記録されるたびに改善サイクルのトリガーを自動判定
"""

import logging
from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TriggerThresholds:
    """トリガー閾値設定"""
    feedback_count_for_analysis: int = 20      # 分析トリガー (フィードバック数)
    feedback_count_for_training: int = 50      # 訓練トリガー (フィードバック数)
    feedback_count_for_ab_test: int = 100      # A/B テストトリガー
    low_rating_threshold: float = 0.6          # 低評価判定閾値 (0-1)
    high_rating_threshold: float = 0.8         # 高評価判定閾値


class FeedbackTriggerSystem:
    """フィードバック駆動型の自動トリガーシステム
    
    フィードバックが記録されるたびに:
    1. 閾値をチェック
    2. 必要なアクション（分析、訓練、最適化等）を特定
    3. コールバック実行
    """
    
    def __init__(self, thresholds: Optional[TriggerThresholds] = None):
        """
        Args:
            thresholds: TriggerThresholds インスタンス
        """
        self.thresholds = thresholds or TriggerThresholds()
        self.callbacks: Dict[str, list] = {
            "on_analysis_needed": [],
            "on_training_needed": [],
            "on_ab_test_needed": [],
            "on_low_rating": [],
            "on_high_rating": [],
            "on_pattern_identified": [],
        }
        logger.info("FeedbackTriggerSystem initialized")
    
    def register_callback(self, event: str, callback: Callable) -> None:
        """トリガーイベントのコールバックを登録
        
        Args:
            event: イベント名 (on_analysis_needed, on_training_needed等)
            callback: 実行するコールバック関数
        """
        if event not in self.callbacks:
            raise ValueError(f"Unknown event: {event}")
        
        if not callable(callback):
            raise ValueError(f"Callback must be callable: {callback}")
        
        self.callbacks[event].append(callback)
        logger.info(f"Registered callback for {event}")
    
    def evaluate_feedback(
        self,
        feedback_count: int,
        average_rating: float,
        improvement_areas: list,
        recent_ratings: list,
    ) -> Dict[str, bool]:
        """フィードバック状態を評価してトリガーを判定
        
        Args:
            feedback_count: 累計フィードバック数
            average_rating: 平均評価 (0-1)
            improvement_areas: 改善領域リスト
            recent_ratings: 最近の評価リスト
        
        Returns:
            {
                "analysis_needed": bool,
                "training_needed": bool,
                "ab_test_needed": bool,
                "immediate_action": bool,
            }
        """
        triggers = {
            "analysis_needed": False,
            "training_needed": False,
            "ab_test_needed": False,
            "immediate_action": False,
            "triggered_reasons": [],
        }
        
        # 1. 分析トリガーチェック
        if feedback_count >= self.thresholds.feedback_count_for_analysis:
            triggers["analysis_needed"] = True
            triggers["triggered_reasons"].append(
                f"Feedback count reached: {feedback_count}/{self.thresholds.feedback_count_for_analysis}"
            )
        
        # 2. 訓練トリガーチェック
        if feedback_count >= self.thresholds.feedback_count_for_training:
            triggers["training_needed"] = True
            triggers["triggered_reasons"].append(
                f"Training threshold reached: {feedback_count}/{self.thresholds.feedback_count_for_training}"
            )
        
        # 3. A/B テストトリガーチェック
        if feedback_count >= self.thresholds.feedback_count_for_ab_test:
            triggers["ab_test_needed"] = True
            triggers["triggered_reasons"].append(
                f"A/B test threshold reached: {feedback_count}/{self.thresholds.feedback_count_for_ab_test}"
            )
        
        # 4. 低評価即時対応トリガー
        if average_rating < self.thresholds.low_rating_threshold:
            triggers["immediate_action"] = True
            triggers["triggered_reasons"].append(
                f"Low rating detected: {average_rating:.2%} < {self.thresholds.low_rating_threshold:.2%}"
            )
        
        # 5. 最近の評価傾向チェック (直近5個が低い)
        if len(recent_ratings) >= 5:
            recent_avg = sum(recent_ratings[-5:]) / 5
            if recent_avg < self.thresholds.low_rating_threshold - 0.1:
                triggers["immediate_action"] = True
                triggers["triggered_reasons"].append(
                    f"Recent trend declining: {recent_avg:.2%}"
                )
        
        # 6. 改善領域が多い場合
        if len(improvement_areas) > 3:
            triggers["analysis_needed"] = True
            triggers["triggered_reasons"].append(
                f"Many improvement areas identified: {len(improvement_areas)}"
            )
        
        return triggers
    
    def execute_triggers(self, triggers: Dict[str, Any]) -> None:
        """評価結果に基づいてコールバックを実行
        
        Args:
            triggers: evaluate_feedback() の戻り値
        """
        reasons = triggers["triggered_reasons"]
        
        if reasons:
            logger.info(f"🔔 Triggers activated: {reasons}")
        
        # 即時対応が最優先
        if triggers["immediate_action"]:
            self._execute_callbacks("on_low_rating")
            logger.warning("⚠️ Immediate action triggered")
        
        # A/Bテストが最優先（訓練より前）
        if triggers["ab_test_needed"]:
            self._execute_callbacks("on_ab_test_needed")
            logger.info("🧪 A/B test triggered")
        
        # 訓練
        if triggers["training_needed"]:
            self._execute_callbacks("on_training_needed")
            logger.info("🧠 Training triggered")
        
        # 分析
        if triggers["analysis_needed"]:
            self._execute_callbacks("on_analysis_needed")
            logger.info("📊 Analysis triggered")
    
    def _execute_callbacks(self, event: str) -> None:
        """指定イベントのすべてのコールバックを実行"""
        callbacks = self.callbacks.get(event, [])
        
        for callback in callbacks:
            try:
                callback()
                logger.debug(f"✅ Executed callback for {event}")
            except Exception as e:
                logger.error(f"❌ Error executing callback for {event}: {e}")
    
    def on_feedback_recorded(
        self,
        feedback_manager,
    ) -> None:
        """フィードバック記録時の自動トリガー実行
        
        実装例:
            trigger_system.on_feedback_recorded(feedback_manager)
        """
        try:
            # 現在の統計を取得
            stats = feedback_manager.get_summary_stats()
            improvement_areas = feedback_manager.get_improvement_areas()
            recent = feedback_manager.get_recent_feedback(10)
            recent_ratings = [f.rating for f in recent]
            
            # トリガー評価
            triggers = self.evaluate_feedback(
                feedback_count=stats["total_count"],
                average_rating=stats["average_rating"],
                improvement_areas=improvement_areas,
                recent_ratings=recent_ratings,
            )
            
            # トリガー実行
            self.execute_triggers(triggers)
            
        except Exception as e:
            logger.error(f"Error in on_feedback_recorded: {e}")


class SafetyGate:
    """改善の安全性ゲート
    
    提案された改善を自動適用する前にチェックを実施
    Phase 2 統合: ロールバック機構との連携
    """
    
    def __init__(self, approval_required: bool = True, rollback_manager=None):
        """
        Args:
            approval_required: True = 人間確認必須、False = 自動適用
            rollback_manager: RollbackManager インスタンス (オプション)
        """
        self.approval_required = approval_required
        self.pending_approvals: Dict[str, Dict[str, Any]] = {}
        self.rollback_manager = rollback_manager
        logger.info(f"SafetyGate initialized (approval_required={approval_required})")
        if rollback_manager:
            logger.info("✅ Rollback manager integrated into SafetyGate")
    
    def check_prompt_change(
        self,
        old_template: str,
        new_template: str,
        reason: str,
    ) -> bool:
        """プロンプト変更の安全性チェック
        
        Args:
            old_template: 変更前テンプレート
            new_template: 変更後テンプレート
            reason: 変更理由
        
        Returns:
            True = 安全 / 適用可, False = 危険 / 要確認
        """
        # 基本チェック
        if not new_template or len(new_template) == 0:
            logger.error("New template is empty")
            return False
        
        # テンプレート長の大幅変更をチェック
        length_ratio = len(new_template) / max(len(old_template), 1)
        if length_ratio > 2.0 or length_ratio < 0.5:
            logger.warning(
                f"Template length changed significantly: "
                f"{len(old_template)} → {len(new_template)} "
                f"(ratio: {length_ratio:.1f})"
            )
        
        logger.info(f"✅ Prompt change safety check passed")
        return True
    
    def check_model_update(
        self,
        performance_delta: float,
        confidence_score: float,
    ) -> bool:
        """モデル更新の安全性チェック
        
        Args:
            performance_delta: 性能改善量 (0.0 ~ 1.0)
            confidence_score: 信頼スコア (0.0 ~ 1.0)
        
        Returns:
            True = 安全 / 適用可, False = 危険 / 要確認
        """
        # 性能が低下する場合は要確認
        if performance_delta < 0:
            logger.warning(
                f"Performance would decrease by {performance_delta:.2%}. Requires review."
            )
            return False
        
        # 信頼度が低い場合
        if confidence_score < 0.7:
            logger.warning(
                f"Confidence score too low: {confidence_score:.2%} < 0.7. Requires review."
            )
            return False
        
        logger.info(f"✅ Model update safety check passed (delta: +{performance_delta:.2%})")
        return True
    
    def request_approval(
        self,
        change_type: str,
        description: str,
        metadata: Dict[str, Any],
    ) -> str:
        """承認リクエストを作成
        
        Args:
            change_type: 変更タイプ (prompt_change, model_update等)
            description: 説明
            metadata: メタデータ
        
        Returns:
            リクエストID
        """
        import uuid
        request_id = str(uuid.uuid4())[:8]
        
        self.pending_approvals[request_id] = {
            "timestamp": datetime.now().isoformat(),
            "change_type": change_type,
            "description": description,
            "metadata": metadata,
            "status": "pending",
        }
        
        logger.info(f"📋 Approval requested: {request_id} ({change_type})")
        return request_id
    
    def approve(self, request_id: str) -> bool:
        """リクエストを承認"""
        if request_id not in self.pending_approvals:
            logger.error(f"Request not found: {request_id}")
            return False
        
        self.pending_approvals[request_id]["status"] = "approved"
        logger.info(f"✅ Approved: {request_id}")
        return True
    
    def reject(self, request_id: str, reason: str = None) -> bool:
        """リクエストを却下"""
        if request_id not in self.pending_approvals:
            logger.error(f"Request not found: {request_id}")
            return False
        
        self.pending_approvals[request_id]["status"] = "rejected"
        self.pending_approvals[request_id]["rejection_reason"] = reason
        logger.warning(f"❌ Rejected: {request_id} - {reason}")
        return True
    
    def request_rollback(
        self,
        reason: str,
        target_checkpoint_id: Optional[str] = None,
        feedbacks: Optional[list] = None,
    ) -> str:
        """Phase 2: ロールバックをリクエスト
        
        Args:
            reason: ロールバック理由
            target_checkpoint_id: 復旧対象チェックポイント ID
            feedbacks: 最近のフィードバック (分析用)
        
        Returns:
            ロールバックリクエスト ID
        """
        if not self.rollback_manager:
            logger.warning("⚠️ Rollback manager not integrated - cannot process rollback request")
            return None
        
        import uuid
        request_id = str(uuid.uuid4())[:8]
        
        # ロールバック必要性を評価
        needs_rollback, analysis = self.rollback_manager.evaluate_rollback_need(
            feedbacks or []
        )
        
        self.pending_approvals[request_id] = {
            "timestamp": datetime.now().isoformat(),
            "change_type": "rollback",
            "description": reason,
            "metadata": {
                "target_checkpoint": target_checkpoint_id,
                "needs_rollback": needs_rollback,
                "analysis": analysis,
            },
            "status": "pending",
        }
        
        logger.warning(f"🔄 Rollback requested: {request_id}")
        logger.warning(f"   Reason: {reason}")
        logger.warning(f"   Analysis: {analysis.get('recommendation')}")
        
        return request_id
    
    def approve_rollback(self, request_id: str) -> bool:
        """ロールバックを承認して実行
        
        Args:
            request_id: ロールバックリクエスト ID
        
        Returns:
            成功したか
        """
        if request_id not in self.pending_approvals:
            logger.error(f"Rollback request not found: {request_id}")
            return False
        
        approval = self.pending_approvals[request_id]
        
        if approval["change_type"] != "rollback":
            logger.error(f"Request {request_id} is not a rollback request")
            return False
        
        if not self.rollback_manager:
            logger.error("Rollback manager not available")
            return False
        
        # ロールバック実行
        target_ckpt = approval["metadata"].get("target_checkpoint")
        reason = approval["description"]
        
        success, result = self.rollback_manager.execute_rollback(
            target_checkpoint_id=target_ckpt,
            reason=reason
        )
        
        approval["status"] = "executed" if success else "failed"
        approval["result"] = result
        
        if success:
            logger.info(f"✅ Rollback executed: {request_id}")
        else:
            logger.error(f"❌ Rollback failed: {request_id}")
        
        return success
    
    def evaluate_rollback_request(self, request_id: str) -> Dict[str, Any]:
        """ロールバック要求の詳細を取得
        
        Args:
            request_id: ロールバックリクエスト ID
        
        Returns:
            {
                "status": "pending|executed|failed",
                "reason": str,
                "analysis": dict,
                "result": dict or None,
                ...
            }
        """
        if request_id not in self.pending_approvals:
            return {"error": "Request not found"}
        
        return self.pending_approvals[request_id]


if __name__ == "__main__":
    # テスト用スタンドアロン実行
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # トリガーシステム作成
    trigger_system = FeedbackTriggerSystem()
    
    # コールバック登録
    def on_analysis_needed():
        logger.info(">>> Executing: Analysis needed")
    
    def on_training_needed():
        logger.info(">>> Executing: Training needed")
    
    trigger_system.register_callback("on_analysis_needed", on_analysis_needed)
    trigger_system.register_callback("on_training_needed", on_training_needed)
    
    # テストシナリオ1: 分析トリガー
    logger.info("\n=== Test Scenario 1: Analysis trigger ===")
    triggers1 = trigger_system.evaluate_feedback(
        feedback_count=25,
        average_rating=0.75,
        improvement_areas=["clarity", "completeness"],
        recent_ratings=[0.7, 0.8, 0.75, 0.8],
    )
    trigger_system.execute_triggers(triggers1)
    
    # テストシナリオ2: 訓練トリガー
    logger.info("\n=== Test Scenario 2: Training trigger ===")
    triggers2 = trigger_system.evaluate_feedback(
        feedback_count=55,
        average_rating=0.72,
        improvement_areas=["clarity", "completeness", "accuracy"],
        recent_ratings=[0.7, 0.8, 0.75, 0.8],
    )
    trigger_system.execute_triggers(triggers2)
    
    # テストシナリオ3: 低評価即時対応
    logger.info("\n=== Test Scenario 3: Low rating, immediate action ===")
    triggers3 = trigger_system.evaluate_feedback(
        feedback_count=30,
        average_rating=0.55,
        improvement_areas=["clarity", "accuracy"],
        recent_ratings=[0.4, 0.5, 0.6, 0.5],
    )
    trigger_system.execute_triggers(triggers3)
    
    # SafetyGate テスト
    logger.info("\n=== SafetyGate Test ===")
    safety_gate = SafetyGate(approval_required=True)
    
    result = safety_gate.check_prompt_change(
        old_template="Template A",
        new_template="Template A with improvements",
        reason="Better clarity"
    )
    logger.info(f"Prompt change safe: {result}")
    
    result = safety_gate.check_model_update(
        performance_delta=0.05,
        confidence_score=0.85,
    )
    logger.info(f"Model update safe: {result}")

    logger.info("\n✅ Test complete")
