"""自立型LLM自動改善スケジューラー

ユーザーフィードバックに基づいた改善サイクルを自動で実行するためのスケジューラー。
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class AutomationScheduler:
    """自動改善スケジューラー
    
    以下のタスクを定期実行：
    1. フィードバック分析 (毎時間)
    2. 改善提案生成 (毎時間)
    3. マイクロファインチューニング (1日1回)
    4. メトリクス更新・検証 (15分ごと)
    5. ロールバック判定 (毎時間)
    """
    
    def __init__(self, log_dir: str = None):
        """
        Args:
            log_dir: ログ保存ディレクトリ
        """
        if log_dir is None:
            log_dir = Path("logs/scheduler")
        
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "scheduler.log"
        self.execution_log_file = self.log_dir / "execution_history.jsonl"
        
        # スケジューラー初期化
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_listener(self._on_job_event)
        
        # タスク登録フック
        self.task_handlers: Dict[str, Callable] = {}
        self.is_running = False
        
        logger.info(f"AutomationScheduler initialized (log_dir={self.log_dir})")
    
    def register_task(self, task_name: str, handler: Callable) -> None:
        """タスクハンドラーを登録
        
        Args:
            task_name: タスク名（task_feedback_analysis等）
            handler: 実行する関数（def handler() -> None）
        """
        if not callable(handler):
            raise ValueError(f"Handler must be callable: {handler}")
        
        self.task_handlers[task_name] = handler
        logger.info(f"Registered task: {task_name}")
    
    def start(self) -> None:
        """スケジューラー開始"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        try:
            self.scheduler.start()
            self.is_running = True
            logger.info("🚀 Scheduler started")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            raise
    
    def stop(self) -> None:
        """スケジューラー停止"""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return
        
        try:
            self.scheduler.shutdown(wait=True)
            self.is_running = False
            logger.info("🛑 Scheduler stopped")
        except Exception as e:
            logger.error(f"Failed to stop scheduler: {e}")
    
    def schedule_feedback_analysis(self, interval_minutes: int = 60) -> None:
        """フィードバック分析を定期実行
        
        Args:
            interval_minutes: 実行間隔（分）
        """
        if "task_feedback_analysis" not in self.task_handlers:
            logger.warning("task_feedback_analysis handler not registered")
            return
        
        self.scheduler.add_job(
            self.task_handlers["task_feedback_analysis"],
            IntervalTrigger(minutes=interval_minutes),
            id="task_feedback_analysis",
            name="Feedback Analysis",
            replace_existing=True,
        )
        logger.info(f"📊 Scheduled feedback analysis every {interval_minutes} minutes")
    
    def schedule_prompt_optimization(self, interval_minutes: int = 60) -> None:
        """プロンプト最適化を定期実行
        
        Args:
            interval_minutes: 実行間隔（分）
        """
        if "task_prompt_optimization" not in self.task_handlers:
            logger.warning("task_prompt_optimization handler not registered")
            return
        
        self.scheduler.add_job(
            self.task_handlers["task_prompt_optimization"],
            IntervalTrigger(minutes=interval_minutes),
            id="task_prompt_optimization",
            name="Prompt Optimization",
            replace_existing=True,
        )
        logger.info(f"✨ Scheduled prompt optimization every {interval_minutes} minutes")
    
    def schedule_continuous_training(self, cron_expression: str = "0 2 * * *") -> None:
        """継続的訓練を定期実行（デフォルト: 毎日午前2時）
        
        Args:
            cron_expression: Cron形式スケジュール式
        """
        if "task_continuous_training" not in self.task_handlers:
            logger.warning("task_continuous_training handler not registered")
            return
        
        self.scheduler.add_job(
            self.task_handlers["task_continuous_training"],
            CronTrigger.from_crontab(cron_expression),
            id="task_continuous_training",
            name="Continuous Training",
            replace_existing=True,
        )
        logger.info(f"🧠 Scheduled continuous training: {cron_expression}")
    
    def schedule_metric_verification(self, interval_minutes: int = 15) -> None:
        """メトリクス検証を定期実行
        
        Args:
            interval_minutes: 実行間隔（分）
        """
        if "task_metric_verification" not in self.task_handlers:
            logger.warning("task_metric_verification handler not registered")
            return
        
        self.scheduler.add_job(
            self.task_handlers["task_metric_verification"],
            IntervalTrigger(minutes=interval_minutes),
            id="task_metric_verification",
            name="Metric Verification",
            replace_existing=True,
        )
        logger.info(f"📈 Scheduled metric verification every {interval_minutes} minutes")
    
    def schedule_rollback_check(self, interval_minutes: int = 60) -> None:
        """ロールバック判定を定期実行
        
        Args:
            interval_minutes: 実行間隔（分）
        """
        if "task_rollback_check" not in self.task_handlers:
            logger.warning("task_rollback_check handler not registered")
            return
        
        self.scheduler.add_job(
            self.task_handlers["task_rollback_check"],
            IntervalTrigger(minutes=interval_minutes),
            id="task_rollback_check",
            name="Rollback Check",
            replace_existing=True,
        )
        logger.info(f"🔄 Scheduled rollback check every {interval_minutes} minutes")
    
    def schedule_ab_testing(self, interval_minutes: int = 240) -> None:
        """A/B テスティングを定期実行 (Phase 3)
        
        Args:
            interval_minutes: 実行間隔（分、デフォルト 240 = 4 時間）
        """
        if "task_ab_testing" not in self.task_handlers:
            logger.warning("task_ab_testing handler not registered")
            return
        
        self.scheduler.add_job(
            self.task_handlers["task_ab_testing"],
            IntervalTrigger(minutes=interval_minutes),
            id="task_ab_testing",
            name="A/B Testing",
            replace_existing=True,
        )
        logger.info(f"🧪 Scheduled A/B testing every {interval_minutes} minutes (Phase 3)")
    
    def get_scheduled_jobs(self) -> list:
        """登録済みジョブ一覧を取得"""
        return self.scheduler.get_jobs()
    
    def pause_job(self, job_id: str) -> None:
        """ジョブを一時停止"""
        try:
            self.scheduler.pause_job(job_id)
            logger.info(f"⏸️ Job paused: {job_id}")
        except Exception as e:
            logger.error(f"Failed to pause job {job_id}: {e}")
    
    def resume_job(self, job_id: str) -> None:
        """ジョブを再開"""
        try:
            self.scheduler.resume_job(job_id)
            logger.info(f"▶️ Job resumed: {job_id}")
        except Exception as e:
            logger.error(f"Failed to resume job {job_id}: {e}")
    
    def _on_job_event(self, event):
        """ジョブ実行イベントハンドラー"""
        if event.exception:
            logger.error(f"❌ Job failed: {event.job_id} - {event.exception}")
            self._log_execution(event.job_id, "FAILED", str(event.exception))
        else:
            logger.info(f"✅ Job executed: {event.job_id}")
            self._log_execution(event.job_id, "SUCCESS", None)
    
    def _log_execution(self, job_id: str, status: str, error: Optional[str]) -> None:
        """実行ログを記録"""
        import json
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "job_id": job_id,
                "status": status,
                "error": error,
            }
            with open(self.execution_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"Failed to write execution log: {e}")


class AutomationEngine:
    """自立型LLMの自動改善エンジン
    
    フィードバックから改善までの一連の処理を調整・実行
    Phase 2 統合: RollbackManager による自動ロールバック
    """
    
    def __init__(
        self,
        feedback_manager: Optional[Any] = None,
        prompt_optimizer: Optional[Any] = None,
        continuous_trainer: Optional[Any] = None,
        metric_tracker: Optional[Any] = None,
        rollback_manager: Optional[Any] = None,
        ab_testing_engine: Optional[Any] = None,
        log_dir: str = None,
    ):
        """
        Args:
            feedback_manager: FeedbackManager インスタンス
            prompt_optimizer: PromptOptimizer インスタンス
            continuous_trainer: ContinuousTrainer インスタンス
            metric_tracker: MetricTracker インスタンス
            rollback_manager: RollbackManager インスタンス (Phase 2)
            ab_testing_engine: ABTestingEngine インスタンス (Phase 3)
            log_dir: ログディレクトリ
        """
        self.feedback_manager = feedback_manager
        self.prompt_optimizer = prompt_optimizer
        self.continuous_trainer = continuous_trainer
        self.metric_tracker = metric_tracker
        self.rollback_manager = rollback_manager
        self.ab_testing_engine = ab_testing_engine
        
        if log_dir is None:
            log_dir = Path("logs/automation")
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # スケジューラー初期化
        self.scheduler = AutomationScheduler(log_dir=str(self.log_dir / "scheduler"))
        self._register_tasks()
        
        logger.info("AutomationEngine initialized")
        if rollback_manager:
            logger.info("✅ Rollback manager integrated into AutomationEngine")
        if ab_testing_engine:
            logger.info("✅ A/B Testing engine integrated into AutomationEngine")
    
    def _register_tasks(self) -> None:
        """スケジューラータスクを登録"""
        self.scheduler.register_task(
            "task_feedback_analysis",
            self.task_analyze_feedback
        )
        self.scheduler.register_task(
            "task_prompt_optimization",
            self.task_optimize_prompts
        )
        self.scheduler.register_task(
            "task_continuous_training",
            self.task_perform_training
        )
        self.scheduler.register_task(
            "task_metric_verification",
            self.task_verify_metrics
        )
        self.scheduler.register_task(
            "task_rollback_check",
            self.task_check_rollback
        )
        self.scheduler.register_task(
            "task_ab_testing",
            self.task_run_ab_test
        )
    
    def task_analyze_feedback(self) -> None:
        """【タスク】フィードバック分析"""
        try:
            if self.feedback_manager is None:
                logger.warning("FeedbackManager not available")
                return
            
            stats = self.feedback_manager.get_summary_stats()
            improvement_areas = self.feedback_manager.get_improvement_areas()
            
            logger.info("📊 Feedback Analysis:")
            logger.info(f"   Total feedback: {stats['total_count']}")
            logger.info(f"   Average rating: {stats['average_rating']:.2%}")
            logger.info(f"   Improvement areas: {improvement_areas}")
            
        except Exception as e:
            logger.error(f"Error in task_analyze_feedback: {e}")
            raise
    
    def task_optimize_prompts(self) -> None:
        """【タスク】プロンプト最適化"""
        try:
            if self.prompt_optimizer is None or self.feedback_manager is None:
                logger.warning("PromptOptimizer or FeedbackManager not available")
                return
            
            # 改善領域を分析
            improvement_areas = self.feedback_manager.get_improvement_areas()
            
            # 低評価フィードバックを取得
            stats = self.feedback_manager.get_summary_stats()
            if stats['average_rating'] < 0.7:
                logger.info("⚠️ Low average rating detected. Optimizing prompts...")
                
                # テンプレート性能を確認
                templates = self.prompt_optimizer.list_templates()
                best_template = self.prompt_optimizer.get_best_template()
                
                logger.info("✨ Prompt Optimization:")
                logger.info(f"   Active templates: {len(templates)}")
                logger.info(f"   Best template: {best_template}")
                logger.info(f"   Improvement areas: {improvement_areas}")
            else:
                logger.info("✅ Prompt quality is acceptable")
        
        except Exception as e:
            logger.error(f"Error in task_optimize_prompts: {e}")
            raise
    
    def task_perform_training(self) -> None:
        """【タスク】マイクロファインチューニング実行"""
        try:
            if self.feedback_manager is None or self.continuous_trainer is None:
                logger.warning("FeedbackManager or ContinuousTrainer not available")
                return
            
            # フィードバック数をチェック
            stats = self.feedback_manager.get_summary_stats()
            total_feedback = stats['total_count']
            
            threshold = 50  # 訓練トリガー閾値
            
            if total_feedback >= threshold:
                logger.info(f"🧠 Training triggered (feedback: {total_feedback} >= {threshold})")
                
                # 訓練データ準備
                high_quality_feedback = self.feedback_manager.get_feedback_by_rating(min_rating=0.7)
                logger.info(f"   Using {len(high_quality_feedback)} high-quality feedback items")
                
                # （実際の訓練実行はここでしたがるが、ここでは検証のみ）
                logger.info(f"   Prepared training dataset with {len(high_quality_feedback)} samples")
            else:
                logger.info(f"⏳ Waiting for more feedback ({total_feedback}/{threshold})")
        
        except Exception as e:
            logger.error(f"Error in task_perform_training: {e}")
            raise
    
    def task_verify_metrics(self) -> None:
        """【タスク】メトリクス検証"""
        try:
            if self.metric_tracker is None:
                logger.warning("MetricTracker not available")
                return
            
            # 現在のダッシュボード状態を取得
            dashboard = self.metric_tracker.get_dashboard()
            current = dashboard.get("current", {})
            
            logger.info("📈 Metrics Verification:")
            logger.info(f"   Average rating: {current.get('average_rating', 'N/A'):.2%}")
            logger.info(f"   Feedback count: {current.get('feedback_count', 0)}")
            logger.info(f"   Training steps: {current.get('training_steps', 0)}")
            logger.info(f"   Improvement: {current.get('improvement_percentage', 0):.1f}%")
        
        except Exception as e:
            logger.error(f"Error in task_verify_metrics: {e}")
            raise
    
    def task_check_rollback(self) -> None:
        """【タスク】ロールバック判定 (Phase 2 強化版)"""
        try:
            if self.metric_tracker is None or self.feedback_manager is None:
                logger.warning("MetricTracker or FeedbackManager not available")
                return
            
            # 最新メトリクスを取得
            dashboard = self.metric_tracker.get_dashboard()
            current = dashboard.get("current", {})
            stats = dashboard.get("statistics", {})
            
            current_rating = current.get('average_rating', 0.5)
            rating_trend = stats.get('rating_trend', 'stable')  # improving, stable, declining
            
            # Phase 2: RollbackManager がある場合、詳細な分析
            if self.rollback_manager:
                try:
                    # 最近のフィードバックを取得
                    recent_feedbacks = self.feedback_manager.get_recent_feedback(limit=20)
                    feedbacks_list = [
                        {
                            "rating": f.rating if hasattr(f, 'rating') else 0.8,
                            "error": f.error if hasattr(f, 'error') else False,
                            "severity": getattr(f, 'severity', 'normal'),
                        }
                        for f in recent_feedbacks
                    ]
                    
                    # ロールバック必要性を評価
                    needs_rollback, analysis = self.rollback_manager.evaluate_rollback_need(
                        feedbacks_list
                    )
                    
                    if needs_rollback:
                        logger.warning(f"🔄 Rollback condition met: {analysis['recommendation']}")
                        logger.warning(f"   Low ratings: {analysis['low_rating_count']}")
                        logger.warning(f"   Rating drop: {analysis['rating_drop_pct']:.1%}")
                        logger.warning(f"   Critical issues: {analysis['critical_issues']}")
                        
                        # 自動実行（推奨に基づく）
                        if analysis['critical_issues'] > 0:
                            logger.error("🚨 CRITICAL: Executing immediate rollback")
                            success, result = self.rollback_manager.execute_rollback(
                                reason="Critical issues detected in feedback"
                            )
                            for step in result.get("steps", []):
                                logger.info(f"   {step}")
                        else:
                            logger.warning("⚠️ Consider rollback - monitoring...")
                    else:
                        logger.info(f"✅ Performance check OK (trend: {rating_trend}, rating: {current_rating:.2%})")
                
                except Exception as e:
                    logger.error(f"RollbackManager evaluation error: {e}")
            else:
                # Phase 1: 基本的なチェック
                if rating_trend == "declining":
                    logger.warning(f"⚠️ Performance declining detected (rating: {current_rating:.2%})")
                    logger.warning("   Consider rollback to previous good state")
                else:
                    logger.info(f"✅ Performance check OK (trend: {rating_trend})")
        
        except Exception as e:
            logger.error(f"Error in task_check_rollback: {e}")
            raise
    
    def task_run_ab_test(self) -> None:
        """【タスク】A/B テスティング実行 (Phase 3)"""
        try:
            if self.ab_testing_engine is None or self.feedback_manager is None:
                logger.warning("ABTestingEngine or FeedbackManager not available for A/B testing")
                return
            
            logger.info("🧪 Starting A/B testing cycle...")
            
            # 最近のフィードバックを取得（Control グループ）
            recent_feedbacks = self.feedback_manager.get_recent_feedback(limit=30)
            if len(recent_feedbacks) < 5:
                logger.warning("Insufficient feedback data (<5 samples) for A/B testing")
                return
            
            # ExperimentResult オブジェクトに変換
            from .ab_testing import ExperimentResult
            baseline_results = [
                ExperimentResult(
                    experiment_id=f"baseline_{i}",
                    candidate_id="baseline",
                    sample_num=i,
                    rating=f.rating if hasattr(f, 'rating') else 0.8,
                    response_time_ms=100.0,  # Placeholder
                    error_occurred=getattr(f, 'error', False),
                    feedback_text=getattr(f, 'text', ''),
                )
                for i, f in enumerate(recent_feedbacks)
            ]
            
            # A/B テスト実行（5 候補、各 30 サンプル）
            test_report = self.ab_testing_engine.run_ab_test(
                test_input="test query",
                inference_fn=self._mock_inference,
                baseline_results=baseline_results,
                num_candidates=5,
                samples_per_candidate=30,
            )
            
            # 結果のサマリー
            best_candidate_id = test_report.get("best_candidate_id")
            best_recommendation = test_report.get("best_recommendation")
            
            if best_recommendation == "ADOPT":
                logger.info(f"✨ A/B test: ADOPT candidate {best_candidate_id}")
                logger.info(f"   Baseline rating: {test_report['baseline_mean_rating']:.3f}")
                
                # 比較結果を確認
                for comp in test_report.get("comparisons", []):
                    if comp.get("candidate_id") == best_candidate_id:
                        logger.info(f"   Improvement: {comp.get('improvement_direction')}")
                        logger.info(f"   Cohen's d: {comp.get('cohens_d'):.3f}")
                        logger.info(f"   p-value: {comp.get('p_value'):.4f}")
                        break
            else:
                logger.info(f"🔍 A/B test: No significant improvement. Best: {best_recommendation}")
                logger.info(f"   Candidates evaluated: {test_report.get('num_candidates')}")
        
        except Exception as e:
            logger.error(f"Error in task_run_ab_test: {e}")
            raise
    
    def _mock_inference(self, input_text: str, prompt_template=None, hyperparameters=None):
        """Mock inference function for A/B testing"""
        # In production: integrate with actual model inference
        import time
        import random
        time.sleep(0.01)  # Simulate latency
        response = f"Response to: {input_text[:30]}..."
        return response, random.uniform(50, 200)  # Return (response, time_ms)
    
    def start_automation(self) -> None:
        """自動改善を開始"""
        logger.info("🚀 Starting autonomous improvement...")
        
        # スケジュール設定
        self.scheduler.schedule_feedback_analysis(interval_minutes=60)
        self.scheduler.schedule_prompt_optimization(interval_minutes=60)
        self.scheduler.schedule_continuous_training(cron_expression="0 2 * * *")  # 毎日午前2時
        self.scheduler.schedule_metric_verification(interval_minutes=15)
        self.scheduler.schedule_rollback_check(interval_minutes=60)
        self.scheduler.schedule_ab_testing(interval_minutes=240)  # 4 hours (Phase 3)
        
        # スケジューラー開始
        self.scheduler.start()
        logger.info("✅ Automation started successfully")
    
    def stop_automation(self) -> None:
        """自動改善を停止"""
        logger.info("🛑 Stopping automation...")
        self.scheduler.stop()
        logger.info("✅ Automation stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """自動化エンジンの状態を取得"""
        jobs = self.scheduler.get_scheduled_jobs()
        
        return {
            "is_running": self.scheduler.is_running,
            "scheduled_jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": str(job.next_run_time) if job.next_run_time else None,
                }
                for job in jobs
            ],
            "total_jobs": len(jobs),
        }


def create_automation_engine(
    feedback_manager=None,
    prompt_optimizer=None,
    continuous_trainer=None,
    metric_tracker=None,
    rollback_manager=None,
    ab_testing_engine=None,
) -> AutomationEngine:
    """ファクトリ関数: AutomationEngine インスタンスを作成
    
    使用例 (Phase 1):
        engine = create_automation_engine(
            feedback_manager=fm,
            prompt_optimizer=po,
            continuous_trainer=ct,
            metric_tracker=mt,
        )
        engine.start_automation()
    
    使用例 (Phase 2):
        engine = create_automation_engine(
            feedback_manager=fm,
            prompt_optimizer=po,
            continuous_trainer=ct,
            metric_tracker=mt,
            rollback_manager=rm,  # RollbackManager 統合
        )
        engine.start_automation()
    
    使用例 (Phase 3):
        engine = create_automation_engine(
            feedback_manager=fm,
            prompt_optimizer=po,
            continuous_trainer=ct,
            metric_tracker=mt,
            rollback_manager=rm,
            ab_testing_engine=ate,  # ABTestingEngine 統合
        )
        engine.start_automation()
    """
    return AutomationEngine(
        feedback_manager=feedback_manager,
        prompt_optimizer=prompt_optimizer,
        continuous_trainer=continuous_trainer,
        metric_tracker=metric_tracker,
        rollback_manager=rollback_manager,
        ab_testing_engine=ab_testing_engine,
    )


if __name__ == "__main__":
    # テスト用スタンドアロン実行
    import time
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # スケジューラー作成
    scheduler = AutomationScheduler()
    
    # テストタスク登録
    def test_task():
        logger.info("Test task executed")
    
    scheduler.register_task("test", test_task)
    
    # スケジュール設定（テスト用: 10秒ごと）
    scheduler.scheduler.add_job(
        test_task,
        IntervalTrigger(seconds=10),
        id="test_job"
    )
    
    # 開始
    scheduler.start()
    
    try:
        logger.info("Scheduler running... Press Ctrl+C to stop")
        # 30秒間実行
        for i in range(3):
            time.sleep(10)
            jobs = scheduler.get_scheduled_jobs()
            logger.info(f"Active jobs: {len(jobs)}")
    finally:
        scheduler.stop()
        logger.info("Test complete")
