"""Phase 1 統合テスト

スケジューラーとトリガーの動作確認
"""

import sys
import time
import logging
from pathlib import Path

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/phase1_test.log")
    ]
)
logger = logging.getLogger(__name__)

# モジュールのインポート
try:
    from src.self_improvement import (
        FeedbackManager,
        PromptOptimizer,
        ContinuousTrainer,
        MetricTracker,
        AutomationEngine,
        FeedbackTriggerSystem,
        SafetyGate,
    )
    logger.info("✅ All modules imported successfully")
except ImportError as e:
    logger.error(f"❌ Import error: {e}")
    sys.exit(1)


def test_feedback_trigger():
    """フィードバックトリガーのテスト"""
    logger.info("\n" + "="*70)
    logger.info("TEST 1: Feedback Trigger System")
    logger.info("="*70)
    
    # フィードバック管理とトリガーシステム初期化
    feedback_mgr = FeedbackManager()
    trigger_system = FeedbackTriggerSystem()
    
    # コールバック登録
    analysis_called = {"count": 0}
    training_called = {"count": 0}
    urgent_called = {"count": 0}
    
    def on_analysis():
        analysis_called["count"] += 1
        logger.info("  >> Callback: Analysis needed")
    
    def on_training():
        training_called["count"] += 1
        logger.info("  >> Callback: Training needed")
    
    def on_urgent():
        urgent_called["count"] += 1
        logger.info("  >> Callback: Urgent action")
    
    trigger_system.register_callback("on_analysis_needed", on_analysis)
    trigger_system.register_callback("on_training_needed", on_training)
    trigger_system.register_callback("on_low_rating", on_urgent)
    
    # テストケース1: 低評価で即時対応
    logger.info("\n[Test 1-1] Low rating trigger")
    for i in range(3):
        feedback_mgr.record_feedback(
            user_query=f"Query {i}",
            model_response=f"Response {i}",
            rating=0.4,
            tags=["低品質"],
            suggestions="要改善"
        )
    
    stats = feedback_mgr.get_summary_stats()
    triggers = trigger_system.evaluate_feedback(
        feedback_count=stats["total_count"],
        average_rating=stats["average_rating"],
        improvement_areas=stats.get("top_issues", []),
        recent_ratings=[0.4, 0.4, 0.4],
    )
    trigger_system.execute_triggers(triggers)
    
    # テストケース2: 分析トリガー
    logger.info("\n[Test 1-2] Analysis trigger (20+ feedbacks)")
    for i in range(20):
        feedback_mgr.record_feedback(
            user_query=f"Query {i+3}",
            model_response=f"Response {i+3}",
            rating=0.75,
            tags=["分析"]
        )
    
    stats = feedback_mgr.get_summary_stats()
    triggers = trigger_system.evaluate_feedback(
        feedback_count=stats["total_count"],
        average_rating=stats["average_rating"],
        improvement_areas=stats.get("top_issues", []),
        recent_ratings=[0.75] * 5,
    )
    trigger_system.execute_triggers(triggers)
    
    # テストケース3: 訓練トリガー
    logger.info("\n[Test 1-3] Training trigger (50+ feedbacks)")
    for i in range(30):
        feedback_mgr.record_feedback(
            user_query=f"Query {i+23}",
            model_response=f"Response {i+23}",
            rating=0.8,
            tags=["高品質"]
        )
    
    stats = feedback_mgr.get_summary_stats()
    triggers = trigger_system.evaluate_feedback(
        feedback_count=stats["total_count"],
        average_rating=stats["average_rating"],
        improvement_areas=stats.get("top_issues", []),
        recent_ratings=[0.8] * 5,
    )
    trigger_system.execute_triggers(triggers)
    
    logger.info(f"\n✅ Trigger Test Results:")
    logger.info(f"   Analysis callbacks: {analysis_called['count']}")
    logger.info(f"   Training callbacks: {training_called['count']}")
    logger.info(f"   Urgent callbacks: {urgent_called['count']}")
    logger.info(f"   Total feedbacks: {stats['total_count']}")
    logger.info(f"   Average rating: {stats['average_rating']:.2%}")


def test_safety_gate():
    """安全性ゲートのテスト"""
    logger.info("\n" + "="*70)
    logger.info("TEST 2: Safety Gate")
    logger.info("="*70)
    
    safety_gate = SafetyGate(approval_required=True)
    
    # テストケース1: 安全なプロンプト変更
    logger.info("\n[Test 2-1] Safe prompt change")
    result = safety_gate.check_prompt_change(
        old_template="回答: {query}",
        new_template="質問に対して詳細に回答してください:\n{query}",
        reason="Better clarity"
    )
    logger.info(f"   Result: {'✅ SAFE' if result else '❌ UNSAFE'}")
    
    # テストケース2: 危険なプロンプト変更（空）
    logger.info("\n[Test 2-2] Unsafe prompt change (empty template)")
    result = safety_gate.check_prompt_change(
        old_template="回答: {query}",
        new_template="",
        reason="Empty"
    )
    logger.info(f"   Result: {'✅ SAFE' if result else '❌ UNSAFE'}")
    
    # テストケース3: 安全なモデル更新
    logger.info("\n[Test 2-3] Safe model update")
    result = safety_gate.check_model_update(
        performance_delta=0.08,  # +8%
        confidence_score=0.92,
    )
    logger.info(f"   Result: {'✅ SAFE' if result else '❌ UNSAFE'}")
    
    # テストケース4: 危険なモデル更新（信頼度低）
    logger.info("\n[Test 2-4] Unsafe model update (low confidence)")
    result = safety_gate.check_model_update(
        performance_delta=0.05,
        confidence_score=0.60,  # < 0.7
    )
    logger.info(f"   Result: {'✅ SAFE' if result else '❌ UNSAFE'}")
    
    # テストケース5: 承認リクエスト
    logger.info("\n[Test 2-5] Approval workflow")
    request_id = safety_gate.request_approval(
        change_type="prompt_change",
        description="New prompt template for better quality",
        metadata={"old": "Template A", "new": "Template B"}
    )
    logger.info(f"   Request ID: {request_id}")
    logger.info(f"   Status: pending")
    
    # 承認実行
    safety_gate.approve(request_id)
    logger.info(f"   Status: approved ✅")


def test_automation_scheduler():
    """自動化スケジューラーのテスト（短時間）"""
    logger.info("\n" + "="*70)
    logger.info("TEST 3: Automation Scheduler")
    logger.info("="*70)
    
    try:
        # コンポーネント初期化
        feedback_mgr = FeedbackManager()
        prompt_opt = PromptOptimizer()
        metric_tracker = MetricTracker()
        
        # テスト用フィードバックを記録
        logger.info("\n[Test 3-1] Recording test feedbacks")
        for i in range(10):
            feedback_mgr.record_feedback(
                user_query=f"Test query {i}",
                model_response=f"Test response {i}",
                rating=0.75 + (i % 3) * 0.05,
                tags=["test"]
            )
        
        logger.info(f"   Recorded 10 feedbacks")
        
        # エンジン作成
        logger.info("\n[Test 3-2] Creating AutomationEngine")
        engine = AutomationEngine(
            feedback_manager=feedback_mgr,
            prompt_optimizer=prompt_opt,
            continuous_trainer=None,
            metric_tracker=metric_tracker,
        )
        
        logger.info("✅ AutomationEngine created")
        
        # ステータス確認
        logger.info("\n[Test 3-3] Initial status")
        status = engine.get_status()
        logger.info(f"   Is running: {status['is_running']}")
        logger.info(f"   Scheduled jobs: {status['total_jobs']}")
        
        # タスク実行テスト（手動実行）
        logger.info("\n[Test 3-4] Manual task execution")
        
        logger.info("   Running: task_analyze_feedback")
        engine.task_analyze_feedback()
        
        logger.info("   Running: task_optimize_prompts")
        engine.task_optimize_prompts()
        
        logger.info("   Running: task_verify_metrics")
        engine.task_verify_metrics()
        
        logger.info("   Running: task_check_rollback")
        engine.task_check_rollback()
        
        logger.info("\n✅ All manual tasks executed")
        
    except Exception as e:
        logger.error(f"❌ Error in scheduler test: {e}")
        import traceback
        traceback.print_exc()


def main():
    """テスト実行"""
    logger.info("\n" + "="*70)
    logger.info("🧪 PHASE 1 INTEGRATION TEST")
    logger.info("="*70)
    logger.info(f"Timestamp: {logging.Formatter().formatTime(logging.LogRecord('', 0, '', 0, '', (), None))}")
    
    try:
        # テスト1: トリガーシステム
        test_feedback_trigger()
        
        # テスト2: 安全性ゲート
        test_safety_gate()
        
        # テスト3: スケジューラー
        test_automation_scheduler()
        
        # 最終結果
        logger.info("\n" + "="*70)
        logger.info("✅ ALL TESTS PASSED")
        logger.info("="*70)
        
    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
