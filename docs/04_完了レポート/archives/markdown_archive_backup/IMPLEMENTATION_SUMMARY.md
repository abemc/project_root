# 🤖 自立型LLM自己改善システム - 実装完了

## 📌 概要

ユーザーのフィードバックを基にLLMが自動的に改善される自立型システムを実装しました。以下の4つの核心機能から構成されています：

## 🏗️ システムアーキテクチャ

```
ユーザー入力
    ↓
LLMモデル（回答生成）
    ↓
  ┌─────┬──────────┬──────────┐
  ↓     ↓          ↓          ↓
フィード回答     プロンプト  メトリクス
バック記録     最適化      追跡
  ↓     ↓          ↓          ↓
  └─────┴──────────┴──────────┘
         ↓
   継続的トレーニング
   (マイクロファインチューニング)
         ↓
   最適化モデル（更新版）
```

## 🎯 実装された主要機能

### 1. **FeedbackManager** (`feedback_manager.py`)
ユーザーのフィードバックを記録・分析

**機能:**
- フィードバック記録（評価、タグ、提案）
- 統計情報の自動計算
- 改善領域の特定
- 訓練用データへの変換

```python
feedback = feedback_manager.record_feedback(
    user_query="質問",
    model_response="回答",
    rating=0.85,
    tags=["正確性", "わかりやすさ"],
    suggestions="改善提案"
)
```

### 2. **PromptOptimizer** (`prompt_optimizer.py`)
プロンプトテンプレートの動的最適化

**機能:**
- デフォルトテンプレート（3種類：基本、詳細、簡潔）
- カスタムテンプレットの登録
- A/Bテストで性能を追跡
- フィードバックから自動最適化

```python
system_prompt, user_prompt = prompt_optimizer.format_prompt(
    query="ユーザーの質問",
    template_name="best"  # 最高性能のテンプレットを自動選択
)
```

### 3. **ContinuousTrainer** (`continuous_training.py`)
マイクロファインチューニングで継続的に重みを更新

**機能:**
- フィードバックを訓練データに変換
- 勾配蓄積による安定な更新
- チェックポイント管理
- 自動訓練トリガー（フィードバック50件以上）

```python
# マイクロファインチューニング実行
result = trainer.micro_finetune(
    training_data,
    learning_rate=1e-5,  # 低学習率で安全に更新
    num_epochs=1,
    batch_size=4
)
```

### 4. **MetricTracker** (`metric_tracker.py`)
改善メトリクスの監視とダッシュボード生成

**機能:**
- メトリクススナップショット記録
- 改善傾向の自動分析
- ダッシュボード生成
- Markdownレポート出力

```python
dashboard = metric_tracker.get_dashboard()
# → 評価スコア推移、損失、改善率などを含むデータ
```

## 📁 ディレクトリ構造

```
src/self_improvement/
├── __init__.py                 # パッケージ初期化
├── feedback_manager.py         # フィードバック管理
├── prompt_optimizer.py         # プロンプト最適化
├── continuous_training.py      # マイクロファインチューニング
├── metric_tracker.py           # メトリクス追跡
├── streamlit_integration.py    # UI コンポーネント
├── config.py                   # 設定ファイル
├── INTEGRATION_GUIDE.md        # app.py 統合ガイド
└── README.md                   # 詳細ドキュメント

tests/
└── test_self_improvement.py    # 統合テストスイート
```

## 🔄 ワークフロー例

```python
# 1. マネージャー初期化
feedback_mgr = FeedbackManager()
prompt_opt = PromptOptimizer()
trainer = ContinuousTrainer(model=your_model)
metrics = MetricTracker()

# 2. ユーザーの質問に回答
response = llm.generate(
    system_prompt, user_prompt
)

# 3. ユーザーがフィードバックを入力
feedback = feedback_mgr.record_feedback(
    user_query=user_input,
    model_response=response,
    rating=0.85,
    tags=["良い点"],
    suggestions="さらに例を追加してください"
)

# 4. テンプレート性能を更新
prompt_opt.update_template_performance("best", 0.85)

# 5. メトリクスを記録
stats = feedback_mgr.get_summary_stats()
metrics.record_snapshot(
    feedback_count=stats["total_count"],
    average_rating=stats["average_rating"],
    training_steps=trainer.current_step,
    model_loss=0.15,
    improvement_percentage=5.0
)

# 6. 訓練をトリガー（フィードバック50件以上）
if trainer.should_trigger_training(
    feedback_mgr.export_for_training(),
    threshold=50
):
    # フィードバックから訓練データを生成
    training_data = trainer.prepare_training_data(
        feedback_mgr.export_for_training(),
        tokenizer=tokenizer
    )
    
    # マイクロファインチューニング実行
    result = trainer.micro_finetune(training_data)
    print(f"訓練完了: {result}")

# 7. 低評価フィードバックから最適化
if len(feedback_mgr.get_feedback_by_rating(max_rating=0.5)) > 0:
    optimized = prompt_opt.generate_optimized_template(
        feedback_mgr.export_for_training(),
        low_rating_threshold=0.5
    )
    print(f"新しいテンプレット生成: {optimized.name}")

# 8. ダッシュボード表示
dashboard = metrics.get_dashboard()
print(f"品質傾向: {dashboard['current']['response_quality_trend']}")
```

## 🎨 Streamlit統合例

```python
import streamlit as st
from src.self_improvement.streamlit_integration import StreamlitIntegration

# フィードバック UI をレンダリング
feedback_result = StreamlitIntegration.render_feedback_ui()

if feedback_result["submitted"]:
    st.session_state.feedback_manager.record_feedback(
        user_query=user_input,
        model_response=response,
        rating=feedback_result["rating"],
        feedback_text=feedback_result["feedback_text"],
        tags=feedback_result["tags"],
        suggestions=feedback_result["suggestions"],
    )

# メトリクスダッシュボード
dashboard = st.session_state.metric_tracker.get_dashboard()
StreamlitIntegration.render_metrics_dashboard(dashboard)

# プロンプト最適化 UI
StreamlitIntegration.render_prompt_optimizer_ui(
    st.session_state.prompt_optimizer,
    st.session_state.feedback_manager
)

# 訓練状態表示
StreamlitIntegration.render_training_status(
    st.session_state.continuous_trainer
)
```

## ✨ 主な特徴

### 1. **自動的な品質改善**
- ユーザーフィードバックから自動的にモデルを最適化
- プロンプトとモデル重みの両方が改善

### 2. **安全な段階的学習**
- 低学習率（1e-5）で微調整
- 勾配蓄積で安定性を向上
- チェックポイント管理で失敗時の復元

### 3. **可視化と監視**
- ダッシュボードで改善推移を表示
- 改善傾向の自動検出
- Markdownレポート出力

### 4. **複数のプロンプト戦略**
- テンプレートの A/B テスト
- クエリタイプに応じた選択
- 最高性能テンプレットの自動選択

## 📊 データ保存先

```
logs/
├── feedback/
│   ├── feedback_history.jsonl    # フィードバック履歴
│   └── feedback_summary.json     # 統計情報
├── prompts/
│   ├── templates.jsonl            # プロンプトテンプレット
│   └── performance.json           # テンプレット性能
└── metrics/
    ├── metrics_history.jsonl     # メトリクス履歴
    └── dashboard.json            # ダッシュボードデータ

checkpoints/micro_finetune/
├── model_step_0.pt               # モデルチェックポイント
├── model_step_100.pt
├── model_step_200.pt
└── checkpoints.jsonl             # チェックポイント情報
```

## 🚀 使用開始方法

### 1. **基本的な統合**

`app.py` に以下を追加：

```python
from src.self_improvement import (
    FeedbackManager,
    PromptOptimizer,
    ContinuousTrainer,
    MetricTracker,
)

# セッション状態に追加
if "feedback_manager" not in st.session_state:
    st.session_state.feedback_manager = FeedbackManager()
if "prompt_optimizer" not in st.session_state:
    st.session_state.prompt_optimizer = PromptOptimizer()
if "continuous_trainer" not in st.session_state:
    st.session_state.continuous_trainer = ContinuousTrainer(model=model)
if "metric_tracker" not in st.session_state:
    st.session_state.metric_tracker = MetricTracker()
```

### 2. **詳細な統合ガイド**

[INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) を参照

### 3. **API リファレンス**

[README.md](README.md) を参照

## 🧪 テスト実行

```bash
cd /home/abemc/project_root
PYTHONPATH=. python tests/test_self_improvement.py
```

**テスト結果:**
- ✅ FeedbackManager
- ✅ PromptOptimizer
- ✅ MetricTracker
- ✅ ContinuousTrainer
- ✅ 統合テスト

すべてのテストが成功しました！

## 💡 ベストプラクティス

### フィードバック収集
✓ 複数の次元で評価（正確性、完全性など）
✓ タグで分類を自動化
✓ 具体的な改善提案を促す

### プロンプト最適化
✓ 複数テンプレットで A/B テスト
✓ 低評価からパターン抽出
✓ 定期的に最適化を実行

### マイクロファインチューニング
✓ 低い学習率使用（1e-5）
✓ 50+ サンプルで訓練
✓ チェックポイント定期保存

### メトリクス追跡
✓ 複数のメトリクスを監視
✓ 定期的にスナップショット記録
✓ 傾向を分析して推奨生成

## 📈 改善の流れ

1. **ユーザーフィードバック増加**
   - 50件以上のフィードバックが蓄積

2. **自動群質化トリガー**
   - 訓練が自動実行
   - 低学習率で安全に重みを更新

3. **プロンプト最適化**
   - 低評価フィードバックから学習
   - 新テンプレット自動生成

4. **品質向上の確認**
   - ダッシュボードで改善を可視化
   - 改善傾向を推奨に反映

## 🔧 次のステップ

1. **app.py に統合** → INTEGRATION_GUIDE.md 参照
2. **設定をカスタマイズ** → config.py を編集
3. **ダッシュボード確認** → StreamlitUI で可視化
4. **本番運用** → 非同期訓練推奨

## 📚 参考資料

- [詳細ドキュメント](README.md)
- [統合ガイド](INTEGRATION_GUIDE.md)
- [テストスイート](../tests/test_self_improvement.py)
- [設定ファイル](config.py)

---

**実装完了日**: 2026年4月10日
**ステータス**: ✅本番対応可能
