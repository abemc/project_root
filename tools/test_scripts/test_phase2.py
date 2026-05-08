"""
Phase 2: ロールバック機構のテスト

テスト項目:
  1. CheckpointVersioning - チェックポイント管理
  2. NegativeFeedbackDetector - ネガティブフィードバック検出
  3. ParameterRecovery - パラメータ復旧
  4. RollbackManager - 統合ロールバック管理
  5. SafetyGate + Rollback 統合
  6. AutomationEngine + Rollback 統合
"""

import logging
import sys
import json
from pathlib import Path
from datetime import datetime

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# src パスを追加
sys.path.insert(0, str(Path(__file__).parent))

from src.self_improvement import (
    RollbackManager,
    CheckpointVersioning,
    NegativeFeedbackDetector,
    CheckpointMetadata,
    SafetyGate,
)


# ================================
# テスト 1: CheckpointVersioning
# ================================

def test_checkpoint_versioning():
    """チェックポイント版管理システムをテスト"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 1: Checkpoint Versioning")
    logger.info("=" * 80)
    
    try:
        # 初期化
        versioning = CheckpointVersioning(checkpoint_dir="checkpoints")
        logger.info("✅ CheckpointVersioning initialized")
        
        # チェックポイント1を登録
        ckpt1 = versioning.register_checkpoint(
            checkpoint_id="ckpt_step_1000",
            metrics={"accuracy": 0.95, "f1": 0.92},
            prompt_templates={"default": "You are a helpful assistant."},
            model_type="sft",
            improvement_applied=False,
            feedback_count=0
        )
        logger.info(f"✅ Registered checkpoint 1: {ckpt1.checkpoint_id}")
        
        # チェックポイント2を登録（改善適用）
        ckpt2 = versioning.register_checkpoint(
            checkpoint_id="ckpt_step_1100",
            metrics={"accuracy": 0.96, "f1": 0.93},
            prompt_templates={"default": "You are a helpful and accurate assistant."},
            model_type="sft",
            parent_checkpoint="ckpt_step_1000",
            improvement_applied=True,
            applied_improvements=["prompt_optimization", "feedback_analysis"],
            feedback_count=25
        )
        logger.info(f"✅ Registered checkpoint 2: {ckpt2.checkpoint_id}")
        
        # チェックポイント3を登録（性能低下）
        ckpt3 = versioning.register_checkpoint(
            checkpoint_id="ckpt_step_1200",
            metrics={"accuracy": 0.92, "f1": 0.88},
            prompt_templates={"default": "You are a fast assistant."},
            model_type="sft",
            parent_checkpoint="ckpt_step_1100",
            improvement_applied=True,
            applied_improvements=["prompt_optimization", "aggressive_training"],
            feedback_count=50
        )
        logger.info(f"✅ Registered checkpoint 3 (degraded): {ckpt3.checkpoint_id}")
        
        # 最新の安定チェックポイントを取得
        latest_stable = versioning.get_latest_stable_checkpoint()
        logger.info(f"✅ Latest stable checkpoint: {latest_stable.checkpoint_id}")
        logger.info(f"   Metrics: {latest_stable.metrics}")
        
        # 最近のチェックポイントを取得
        recent = versioning.get_recent_checkpoints(count=2)
        logger.info(f"✅ Recent checkpoints: {[c.checkpoint_id for c in recent]}")
        
        # ロールバックをマーク
        versioning.mark_rollback("ckpt_step_1200", "Performance degradation detected")
        logger.info(f"✅ Marked checkpoint 3 as rolled back")
        
        # 最新の安定チェックポイント（ロールバック後）
        latest_stable_after = versioning.get_latest_stable_checkpoint()
        logger.info(f"✅ Latest stable after rollback: {latest_stable_after.checkpoint_id}")
        
        logger.info("✅ TEST 1 PASSED: Checkpoint Versioning")
        return True
        
    except Exception as e:
        logger.error(f"❌ TEST 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


# ================================
# テスト 2: NegativeFeedbackDetector
# ================================

def test_negative_feedback_detector():
    """ネガティブフィードバック検出をテスト"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Negative Feedback Detector")
    logger.info("=" * 80)
    
    try:
        detector = NegativeFeedbackDetector()
        logger.info("✅ NegativeFeedbackDetector initialized")
        
        # テストシナリオ 1: 正常フィードバック
        logger.info("\n--- Scenario 1: Normal feedback ---")
        recent_fb_1 = [
            {"rating": 0.8, "error": False},
            {"rating": 0.85, "error": False},
            {"rating": 0.82, "error": False},
            {"rating": 0.88, "error": False},
            {"rating": 0.81, "error": False},
        ]
        is_negative_1, indicator_1 = detector.analyze_feedback(
            recent_fb_1,
            previous_avg_rating=0.85,
        )
        logger.info(f"   Result: is_negative={is_negative_1}")
        logger.info(f"   Recommendation: {indicator_1.recommendation}")
        assert not is_negative_1, "Should not be negative"
        
        # テストシナリオ 2: 低評価フィードバック
        logger.info("\n--- Scenario 2: Low rating feedback ---")
        recent_fb_2 = [
            {"rating": 0.3, "error": True},
            {"rating": 0.4, "error": True},
            {"rating": 0.5, "error": False},
            {"rating": 0.35, "error": True},
            {"rating": 0.45, "error": False},
        ]
        is_negative_2, indicator_2 = detector.analyze_feedback(
            recent_fb_2,
            previous_avg_rating=0.85,
        )
        logger.info(f"   Result: is_negative={is_negative_2}")
        logger.info(f"   Low rating count: {indicator_2.low_rating_count}")
        logger.info(f"   Rating drop: {indicator_2.average_rating_drop:.1%}")
        logger.info(f"   Recommendation: {indicator_2.recommendation}")
        assert is_negative_2, "Should be negative"
        
        # テストシナリオ 3: 重大問題
        logger.info("\n--- Scenario 3: Critical issues ---")
        recent_fb_3 = [
            {"rating": 0.7, "error": False, "severity": "critical"},
            {"rating": 0.75, "error": False, "severity": "normal"},
            {"rating": 0.8, "error": False, "severity": "normal"},
            {"rating": 0.72, "error": False, "severity": "normal"},
            {"rating": 0.76, "error": False, "severity": "normal"},
        ]
        is_negative_3, indicator_3 = detector.analyze_feedback(
            recent_fb_3,
            previous_avg_rating=0.8,
        )
        logger.info(f"   Result: is_negative={is_negative_3}")
        logger.info(f"   Critical issues: {indicator_3.critical_issue_count}")
        logger.info(f"   Recommendation: {indicator_3.recommendation}")
        assert is_negative_3, "Should be negative (critical issues)"
        
        logger.info("✅ TEST 2 PASSED: Negative Feedback Detector")
        return True
        
    except Exception as e:
        logger.error(f"❌ TEST 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


# ================================
# テスト 3: RollbackManager
# ================================

def test_rollback_manager():
    """ロールバック管理をテスト"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Rollback Manager")
    logger.info("=" * 80)
    
    try:
        # RollbackManager 初期化
        rollback_mgr = RollbackManager(checkpoint_dir="checkpoints")
        logger.info("✅ RollbackManager initialized")
        
        # チェックポイントを登録
        ckpt = rollback_mgr.create_manual_checkpoint(
            checkpoint_id="test_ckpt_001",
            metrics={"accuracy": 0.95},
            prompt_templates={"default": "Test template"},
            model_type="sft",
            description="Test checkpoint"
        )
        logger.info(f"✅ Created checkpoint: {ckpt.checkpoint_id}")
        
        # ステータスを確認
        status = rollback_mgr.get_rollback_status()
        logger.info(f"✅ Rollback status retrieved:")
        logger.info(f"   Total checkpoints: {status['total_checkpoints']}")
        logger.info(f"   Stable checkpoints: {status['stable_checkpoints']}")
        logger.info(f"   Rollback history: {status['rollback_history_count']}")
        
        # ロールバック必要性を評価
        test_feedbacks = [
            {"rating": 0.3, "error": True},
            {"rating": 0.4, "error": True},
            {"rating": 0.5, "error": False},
            {"rating": 0.35, "error": True},
            {"rating": 0.45, "error": False},
        ]
        needs_rollback, report = rollback_mgr.evaluate_rollback_need(test_feedbacks)
        logger.info(f"✅ Rollback evaluation:")
        logger.info(f"   Needs rollback: {needs_rollback}")
        logger.info(f"   Recommendation: {report.get('recommendation')}")
        logger.info(f"   Rating drop: {report.get('rating_drop_pct'):.1%}")
        logger.info(f"   Critical issues: {report.get('critical_issues')}")
        
        # ロールバック実行（シミュレーション）
        logger.info("\n--- Simulating rollback execution ---")
        success, result = rollback_mgr.execute_rollback(
            target_checkpoint_id="test_ckpt_001",
            reason="Performance degradation detected"
        )
        logger.info(f"✅ Rollback execution:")
        logger.info(f"   Success: {success}")
        for step in result.get("steps", []):
            logger.info(f"   {step}")
        
        logger.info("✅ TEST 3 PASSED: Rollback Manager")
        return True
        
    except Exception as e:
        logger.error(f"❌ TEST 3 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


# ================================
# テスト 4: SafetyGate + Rollback 統合
# ================================

def test_safetygate_rollback_integration():
    """SafetyGate とロールバック機構の統合をテスト"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: SafetyGate + Rollback Integration")
    logger.info("=" * 80)
    
    try:
        # RollbackManager を初期化
        rollback_mgr = RollbackManager(checkpoint_dir="checkpoints")
        
        # SafetyGate をロールバック管理と統合
        safety_gate = SafetyGate(approval_required=True, rollback_manager=rollback_mgr)
        logger.info("✅ SafetyGate initialized with rollback manager")
        
        # チェックポイントを作成
        test_ckpt = rollback_mgr.create_manual_checkpoint(
            checkpoint_id="safetygate_test_001",
            metrics={"accuracy": 0.95},
            prompt_templates={"default": "Safety test template"},
            model_type="sft"
        )
        logger.info(f"✅ Created test checkpoint: {test_ckpt.checkpoint_id}")
        
        # テストシナリオ 1: ロールバックリクエスト
        logger.info("\n--- Scenario 1: Request rollback ---")
        test_feedbacks = [
            {"rating": 0.3, "error": True},
            {"rating": 0.4, "error": True},
            {"rating": 0.5, "error": False},
            {"rating": 0.35, "error": True},
            {"rating": 0.45, "error": False},
        ]
        rollback_request_id = safety_gate.request_rollback(
            reason="Critical performance degradation",
            target_checkpoint_id="safetygate_test_001",
            feedbacks=test_feedbacks
        )
        logger.info(f"✅ Rollback requested: {rollback_request_id}")
        
        # リクエスト詳細を確認
        rollback_info = safety_gate.evaluate_rollback_request(rollback_request_id)
        logger.info(f"✅ Rollback info:")
        logger.info(f"   Status: {rollback_info['status']}")
        logger.info(f"   Recommendation: {rollback_info['metadata']['analysis']['recommendation']}")
        
        # ロールバック承認を実行
        logger.info("\n--- Approving rollback ---")
        approval_success = safety_gate.approve_rollback(rollback_request_id)
        logger.info(f"✅ Rollback approval result: {approval_success}")
        
        # テストシナリオ 2: プロンプト変更
        logger.info("\n--- Scenario 2: Prompt change safety check ---")
        old_template = "You are an assistant."
        new_template = "You are a helpful and accurate assistant that provides detailed explanations."
        
        is_safe = safety_gate.check_prompt_change(
            old_template=old_template,
            new_template=new_template,
            reason="Improved clarity and accuracy"
        )
        logger.info(f"✅ Prompt change safety: {is_safe}")
        
        # テストシナリオ 3: モデル更新チェック
        logger.info("\n--- Scenario 3: Model update safety check ---")
        is_safe_update = safety_gate.check_model_update(
            performance_delta=0.05,  # +5% 改善
            confidence_score=0.88
        )
        logger.info(f"✅ Model update safety: {is_safe_update}")
        
        logger.info("✅ TEST 4 PASSED: SafetyGate + Rollback Integration")
        return True
        
    except Exception as e:
        logger.error(f"❌ TEST 4 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


# ================================
# メインテスト実行
# ================================

def main():
    """すべてのテストを実行"""
    logger.info("=" * 80)
    logger.info("PHASE 2 TEST SUITE: Rollback Mechanism")
    logger.info("=" * 80)
    
    results = []
    
    # テスト実行
    results.append(("Checkpoint Versioning", test_checkpoint_versioning()))
    results.append(("Negative Feedback Detector", test_negative_feedback_detector()))
    results.append(("Rollback Manager", test_rollback_manager()))
    results.append(("SafetyGate + Rollback", test_safetygate_rollback_integration()))
    
    # 結果サマリー
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{status}: {test_name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    logger.info("=" * 80)
    logger.info(f"Total: {passed} passed, {failed} failed out of {len(results)} tests")
    
    if failed == 0:
        logger.info("🎉 ALL TESTS PASSED!")
        return 0
    else:
        logger.error(f"❌ {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
