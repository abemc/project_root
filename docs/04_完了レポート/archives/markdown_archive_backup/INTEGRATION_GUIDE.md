"""自立型LLM自己改善統合ガイド

このファイルはapp.pyに統合するサンプルコードを提供します。
既存のapp.pyに以下の機能を追加してください。
"""

# =============================================================================
# app.pyに追加する内容（サンプル）
# =============================================================================

"""
既存のインポートに追加:

from src.self_improvement import (
    FeedbackManager,
    PromptOptimizer,
    ContinuousTrainer,
    MetricTracker,
)
from src.self_improvement.streamlit_integration import StreamlitIntegration


# セッション状態の初期化セクションに追加:

# 自立型改善システムの初期化
if "feedback_manager" not in st.session_state:
    st.session_state.feedback_manager = FeedbackManager()

if "prompt_optimizer" not in st.session_state:
    st.session_state.prompt_optimizer = PromptOptimizer()

if "metric_tracker" not in st.session_state:
    st.session_state.metric_tracker = MetricTracker()

if "continuous_trainer" not in st.session_state:
    # モデルがロード済みの場合
    st.session_state.continuous_trainer = ContinuousTrainer(
        model=st.session_state.model if "model" in st.session_state else None
    )


# サイドバーの設定セクションに新しいエキスパンダーを追加:

with st.expander("🔄 自立型改善設定", expanded=False):
    st.subheader("フィードバック・最適化設定")
    
    enable_feedback = st.checkbox(
        "フィードバック機能を有効にする",
        value=True,
        help="ユーザーの評価を記録し、モデル改善に使用します"
    )
    
    auto_optimize_prompt = st.checkbox(
        "プロンプト自動最適化を有効にする",
        value=False,
        help="フィードバックを基に自動的にプロンプトを最適化します"
    )
    
    auto_trigger_training = st.checkbox(
        "自動訓練トリガーを有効にする",
        value=False,
        help="十分なフィードバックが集まると自動的に訓練を開始します"
    )
    
    feedback_threshold = st.number_input(
        "訓練をトリガーするフィードバック数",
        min_value=10,
        max_value=500,
        value=50,
        step=10
    )


# メインのチャット処理ループに追加（回答生成後）:

if st.session_state.enable_feedback and response_generated:
    st.divider()
    feedback_result = StreamlitIntegration.render_feedback_ui()
    
    if feedback_result["submitted"]:
        # フィードバック記録
        feedback = st.session_state.feedback_manager.record_feedback(
            user_query=user_input,
            model_response=response,
            rating=feedback_result["rating"],
            feedback_text=feedback_result["feedback_text"],
            tags=feedback_result["tags"],
            suggestions=feedback_result["suggestions"],
        )
        
        st.success(f"フィードバックを記録しました (ID: {feedback.id})")
        
        # プロンプト最適化の実行
        if st.session_state.auto_optimize_prompt:
            with st.spinner("プロンプトを最適化中..."):
                feedback_items = st.session_state.feedback_manager.export_for_training()
                optimized = st.session_state.prompt_optimizer.generate_optimized_template(
                    feedback_items,
                    low_rating_threshold=0.5
                )
                if optimized:
                    st.info(f"✨ プロンプトが最適化されました: {optimized.name}")
        
        # テンプレート性能を更新
        current_template = "best"  # または使用したテンプレート名
        st.session_state.prompt_optimizer.update_template_performance(
            current_template,
            feedback_result["rating"]
        )
        
        # メトリクス記録
        feedback_stats = st.session_state.feedback_manager.get_summary_stats()
        st.session_state.metric_tracker.record_snapshot(
            feedback_count=feedback_stats["total_count"],
            average_rating=feedback_stats["average_rating"],
            training_steps=st.session_state.continuous_trainer.current_step,
            model_loss=0.0,  # 実際の損失を取得
            improvement_percentage=0.0,
        )
        
        # 自動訓練の判定
        if st.session_state.auto_trigger_training:
            if st.session_state.continuous_trainer.should_trigger_training(
                feedback_items,
                threshold=st.session_state.feedback_threshold
            ):
                st.info("🤖 十分なフィードバックが集まりました。訓練を開始します...")
                
                # 訓練実行（非同期推奨）
                try:
                    # 訓練データの準備
                    training_data = st.session_state.continuous_trainer.prepare_training_data(
                        feedback_items,
                        tokenizer=tokenizer,  # 既存のトークナイザーを使用
                    )
                    
                    # マイクロファインチューニング実行
                    result = st.session_state.continuous_trainer.micro_finetune(
                        training_data,
                        learning_rate=1e-5,
                        num_epochs=1,
                        batch_size=4,
                        gradient_accumulation_steps=2,
                    )
                    
                    st.success(f"訓練完了: {result}")
                
                except Exception as e:
                    st.error(f"訓練エラー: {e}")


# 新しいタブを追加: 改善ダッシュボード

tab_dashboard, tab_prompts, tab_training = st.tabs([
    "📊 改善ダッシュボード",
    "🧠 プロンプト最適化",
    "🤖 訓練管理"
])

with tab_dashboard:
    st.subheader("改善メトリクス")
    dashboard = st.session_state.metric_tracker.get_dashboard()
    StreamlitIntegration.render_metrics_dashboard(dashboard)
    
    # フィードバック統計
    st.subheader("フィードバック統計")
    feedback_stats = st.session_state.feedback_manager.get_summary_stats()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("総フィードバック数", feedback_stats["total_count"])
    with col2:
        st.metric("平均評価", f"{feedback_stats['average_rating']:.2%}")
    with col3:
        st.metric("中央値", f"{feedback_stats['median_rating']:.2%}")
    
    # 評価分布
    if feedback_stats["total_count"] > 0:
        dist = feedback_stats["rating_distribution"]
        fig = px.bar(
            x=list(dist.keys()),
            y=list(dist.values()),
            title="評価スコア分布",
            labels={"x": "スコア範囲", "y": "数"}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # 改善領域
    improvement_areas = st.session_state.feedback_manager.get_improvement_areas()
    if improvement_areas:
        st.subheader("改善が必要な領域")
        for area in improvement_areas:
            st.warning(f"• {area}")

with tab_prompts:
    StreamlitIntegration.render_prompt_optimizer_ui(
        st.session_state.prompt_optimizer,
        st.session_state.feedback_manager,
    )

with tab_training:
    st.subheader("マイクロファインチューニング")
    
    if st.button("📚 訓練データをエクスポート"):
        training_data = st.session_state.feedback_manager.export_for_training()
        st.json({
            "count": len(training_data),
            "sample": training_data[0] if training_data else None
        })
    
    st.divider()
    
    if st.button("🚀 マイクロファインチューニングを実行"):
        with st.spinner("訓練中..."):
            try:
                feedback_items = st.session_state.feedback_manager.export_for_training()
                training_data = st.session_state.continuous_trainer.prepare_training_data(
                    feedback_items,
                    tokenizer=tokenizer,
                )
                
                result = st.session_state.continuous_trainer.micro_finetune(
                    training_data,
                    learning_rate=1e-5,
                    num_epochs=1,
                )
                
                st.success("訓練完了!")
                st.json(result)
            except Exception as e:
                st.error(f"エラー: {e}")
    
    st.divider()
    
    StreamlitIntegration.render_training_status(
        st.session_state.continuous_trainer
    )
    
    # レポート生成
    if st.button("📋 メトリクスレポートを生成"):
        report = st.session_state.metric_tracker.export_metrics()
        st.markdown(report)
        st.download_button(
            label="レポートをダウンロード",
            data=report,
            file_name=f"metrics_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        )
"""

# =============================================================================
# 統合のチェックリスト
# =============================================================================

INTEGRATION_CHECKLIST = """
## 統合チェックリスト

1. **インポートの追加**
   - [ ] src.self_improvementモジュールをインポート
   - [ ] streamlit_integrationをインポート

2. **セッション状態の初期化**
   - [ ] FeedbackManagerの初期化
   - [ ] PromptOptimizerの初期化
   - [ ] ContinuousTrainerの初期化
   - [ ] MetricTrackerの初期化

3. **UIコンポーネントの追加**
   - [ ] サイドバーに自立型改善設定を追加
   - [ ] メインの回答生成後にフィードバックUIを追加
   - [ ] 改善ダッシュボードタブを追加
   - [ ] プロンプト最適化タブを追加
   - [ ] 訓練管理タブを追加

4. **ロジック統合**
   - [ ] フィードバック記録ロジック
   - [ ] プロンプト自動最適化ロジック
   - [ ] テンプレート性能更新ロジック
   - [ ] メトリクス追跡ロジック
   - [ ] 自動訓練トリガー

5. **テスト**
   - [ ] フィードバック録音テスト
   - [ ] プロンプト最適化テスト
   - [ ] ダッシュボード表示テスト
   - [ ] 訓練実行テスト

6. **パフォーマンスチューニング**
   - [ ] 非同期処理（訓練）の検討
   - [ ] メモリ使用量の最適化
   - [ ] キャッシング戦略の実装
"""

if __name__ == "__main__":
    print(INTEGRATION_CHECKLIST)
