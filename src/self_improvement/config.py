"""設定モジュール"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class FeedbackConfig:
    """フィードバック設定"""
    storage_dir: str = "logs/feedback"
    min_rating: float = 0.7
    percentile_threshold: float = 25.0
    
    # フィードバック分分類用の標準タグ
    standard_tags: List[str] = field(default_factory=lambda: [
        "正確性",
        "完全性",
        "わかりやすさ",
        "有用性",
        "長さが適切",
        "言語の質",
        "改善が必要",
        "優秀な回答",
        "例の不足",
        "複雑すぎる",
        "簡潔すぎる",
        "専門用語が多い",
    ])


@dataclass
class PromptConfig:
    """プロンプト最適化設定"""
    storage_dir: str = "logs/prompts"
    default_template: str = "{context}\n\n質問: {query}\n\n答え:"
    default_system_prompt: str = "あなたは有用で正確なアシスタントです。"
    
    # テンプレートの種類
    template_types: List[str] = field(default_factory=lambda: [
        "default",
        "detailed",
        "concise",
        "creative",
        "technical",
    ])


@dataclass
class TrainingConfig:
    """訓練設定"""
    storage_dir: str = "checkpoints/micro_finetune"
    learning_rate: float = 1e-5
    num_epochs: int = 1
    batch_size: int = 4
    gradient_accumulation_steps: int = 2
    warmup_steps: int = 0
    max_length: int = 512
    
    # トレーニングトリガー設定
    trigger_threshold: int = 50  # このサンプル数に達したら訓練
    min_rating_for_training: float = 0.7  # 訓練に使用するサンプルの最小評価
    
    # チェックポイント管理
    max_checkpoints: int = 10  # 保持する最大チェックポイント数
    checkpoint_interval: int = 200  # ステップ間隔でチェックポイント保存


@dataclass
class MetricsConfig:
    """メトリクス設定"""
    storage_dir: str = "logs/metrics"
    snapshot_interval: int = 10  # ハーフことスナップショット間隔（フィードバック/訓練イベント）
    dashboard_refresh_interval: int = 5  # ダッシュボード更新間隔（分）
    
    # トレンド分析
    window_size: int = 24  # 時系列ウィンドウサイズ（スナップショット数）
    improvement_threshold: float = 0.05  # 改善と判定する閾値（5%）
    
    # アラート設定
    alert_low_rating_threshold: float = 0.5  # 低評価アラート閾値
    alert_low_improvement_threshold: float = -0.05  # 低下アラート閾値
    
    # アーカイブ設定
    archive_enabled: bool = True  # アーカイブ機能の有効化
    retention_days: int = 90  # 保持期間（日）
    archive_dir: str = "logs/metrics/archive"  # アーカイブディレクトリ
    max_file_size_mb: int = 100  # ファイルサイズ上限（MB）
    auto_cleanup: bool = True  # 古いアーカイブの自動削除


# デフォルト設定
DEFAULT_CONFIG = {
    "feedback": FeedbackConfig(),
    "prompt": PromptConfig(),
    "training": TrainingConfig(),
    "metrics": MetricsConfig(),
}


def get_config(component: str):
    """設定を取得"""
    return DEFAULT_CONFIG.get(component.lower(),   DEFAULT_CONFIG)


def update_config(component: str, **kwargs):
    """設定を更新"""
    if component.lower() in DEFAULT_CONFIG:
        config_obj = DEFAULT_CONFIG[component.lower()]
        for key, value in kwargs.items():
            if hasattr(config_obj, key):
                setattr(config_obj, key, value)
