"""自立型LLM自己改善モジュール

このパッケージは、ユーザーフィードバックを基にLLMが自動的に改善する仕組みを提供します：
- フィードバック記録と分析
- プロンプトの動的最適化
- 継続的なマイクロファインチューニング
- メトリクス監視
- Phase 2: ロールバック機構による安全性管理
- Phase 3: Auto A/B Testing による最適化候補の自動評価
- Phase 4: Dashboard と Audit ログシステム
- Phase 5: デプロイメント、リソース最適化、コスト分析システム
"""

from .feedback_manager import FeedbackManager
from .value_tuning import infer_value_signals, aggregate_value_signals
from .prompt_optimizer import PromptOptimizer
from .continuous_training import ContinuousTrainer
from .metric_tracker import MetricTracker
from .error_learning import ErrorLearner, ErrorCategory, ErrorRecord, ErrorPattern

# APScheduler はオプショナル
try:
    from .scheduler import AutomationScheduler, AutomationEngine, create_automation_engine
except ImportError:
    AutomationScheduler = None
    AutomationEngine = None
    create_automation_engine = None

from .triggers import FeedbackTriggerSystem, SafetyGate, TriggerThresholds
from .rollback_manager import (
    RollbackManager,
    CheckpointVersioning,
    NegativeFeedbackDetector,
    ParameterRecovery,
    CheckpointMetadata,
    NegativeFeedbackIndicator,
)
from .ab_testing import (
    ABTestingEngine,
    CandidateGenerator,
    ExperimentManager,
    StatisticalAnalyzer,
    CandidateVariation,
    ExperimentResult,
    CandidateAnalysis,
    ComparisonResult,
)
from .audit_logger import (
    AuditLogger,
    AuditEvent,
    AlertRule,
    EventType,
    AlertSeverity,
)
from .dashboard_metrics import (
    DashboardMetrics,
    MetricSnapshot,
)
from .dashboard_ui import (
    DashboardUI,
    DashboardPageBuilder,
)
# Phase 5
from .deployment_manager import (
    DeploymentManager,
    DeploymentConfig,
    DeploymentEnvironment,
    DeploymentStatus,
    DeploymentPipeline,
    DeploymentRecovery,
    ArtifactType,
)
from .resource_optimizer import (
    ResourceOptimizer,
    ResourceMetrics,
    OptimizationStrategy,
    TokenOptimizer,
    InferenceOptimizer,
    BatchOptimizer,
)
from .cost_analyzer import (
    CostAnalyzer,
    CostModel,
    BillingRecord,
    BudgetManager,
    CostBreakdown,
    BillingPeriod,
)

# Phase 6: Environment Adaptation
try:
    from .environment_adapter import (
        QueryAnalyzer,
        AdaptiveParameterTuner,
        AdaptiveModelSelector,
        EnvironmentAdapter,
    )
except ImportError:
    pass

# Phase 7: Multi-domain Knowledge Management
try:
    from .context_analyzer import (
        ContextAnalyzer,
        ImplicitIntentDetector,
        MetaContextTracker,
    )
    from .domain_knowledge import (
        DomainKnowledgeManager,
        CrossDomainLinker,
        DomainIndexer,
    )
    from .reasoning_engine import (
        KnowledgeIntegrator,
        CausalReasoningEngine,
        UncertaintyManager,
    )
except ImportError:
    pass

__all__ = [
    "FeedbackManager",
    "infer_value_signals",
    "aggregate_value_signals",
    "PromptOptimizer",
    "ContinuousTrainer",
    "MetricTracker",
    "AutomationScheduler",
    "AutomationEngine",
    "create_automation_engine",
    "FeedbackTriggerSystem",
    "SafetyGate",
    "TriggerThresholds",
    # Phase 2
    "RollbackManager",
    "CheckpointVersioning",
    "NegativeFeedbackDetector",
    "ParameterRecovery",
    "CheckpointMetadata",
    "NegativeFeedbackIndicator",
    # Phase 3
    "ABTestingEngine",
    "CandidateGenerator",
    "ExperimentManager",
    "StatisticalAnalyzer",
    "CandidateVariation",
    "ExperimentResult",
    "CandidateAnalysis",
    "ComparisonResult",
    # Phase 4
    "AuditLogger",
    "AuditEvent",
    "AlertRule",
    "EventType",
    "AlertSeverity",
    "DashboardMetrics",
    "MetricSnapshot",
    "DashboardUI",
    "DashboardPageBuilder",
    # Phase 5
    "DeploymentManager",
    "DeploymentConfig",
    "DeploymentEnvironment",
    "DeploymentStatus",
    "DeploymentPipeline",
    "DeploymentRecovery",
    "ArtifactType",
    "ResourceOptimizer",
    "ResourceMetrics",
    "OptimizationStrategy",
    "TokenOptimizer",
    "InferenceOptimizer",
    "BatchOptimizer",
    "CostAnalyzer",
    "CostModel",
    "BillingRecord",
    "BudgetManager",
    "CostBreakdown",
    "BillingPeriod",
    # Phase 6
    "QueryAnalyzer",
    "AdaptiveParameterTuner",
    "AdaptiveModelSelector",
    "EnvironmentAdapter",
    # Phase 7
    "ContextAnalyzer",
    "ImplicitIntentDetector",
    "MetaContextTracker",
    "DomainKnowledgeManager",
    "CrossDomainLinker",
    "DomainIndexer",
    "KnowledgeIntegrator",
    "CausalReasoningEngine",
    "UncertaintyManager",
]
