"""Streamlit統合用ユーティリティ"""

import streamlit as st
from typing import Dict, Any
import plotly.graph_objects as go
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class StreamlitIntegration:
    """Streamlitへの統合ユーティリティ"""
    
    @staticmethod
    def render_feedback_ui(session_state_key: str = "feedback_form"):
        """フィードバック入力UIをレンダリング"""
        st.subheader("💬 回答フィードバック")
        
        with st.form("feedback_form", clear_on_submit=True):
            # 評価スライダー
            rating = st.slider(
                "この回答の品質は？",
                0.0, 1.0, 0.5, 0.05,
                help="0 = 不満足、1 = 完璧"
            )
            
            # フィードバックテキスト
            feedback_text = st.text_area(
                "フィードバック（オプション）",
                placeholder="改善してほしい点や良かった点などを自由に記入してください",
                height=100
            )
            
            # タグ選択
            available_tags = [
                "正確性",
                "完全性",
                "わかりやすさ",
                "有用性",
                "長さが適切",
                "言語の質",
                "改善が必要",
                "優秀な回答"
            ]
            
            tags = st.multiselect(
                "タグを選択（複数可）",
                available_tags,
                help="この回答に該当するタグを選択してください"
            )
            
            # 提案
            suggestions = st.text_area(
                "改善提案（オプション）",
                placeholder="より良い回答にするための具体的な提案があれば入力してください",
                height=80
            )
            
            submitted = st.form_submit_button("✅ フィードバック送信")
            
        return {
            "submitted": submitted,
            "rating": rating,
            "feedback_text": feedback_text,
            "tags": tags,
            "suggestions": suggestions,
        }
    
    @staticmethod
    def render_metrics_dashboard(dashboard: Dict[str, Any]):
        """メトリクスダッシュボードをレンダリング"""
        st.subheader("📊 改善メトリクス")
        
        # KPI表示
        col1, col2, col3, col4 = st.columns(4)
        
        current = dashboard.get("current", {})
        stats = dashboard.get("statistics", {})
        
        with col1:
            st.metric(
                "平均評価",
                f"{current.get('average_rating', 0):.1%}",
                delta=f"{stats.get('rating_improvement_percent', 0):.1f}%"
            )
        
        with col2:
            st.metric(
                "フィードバック数",
                current.get("feedback_count", 0)
            )
        
        with col3:
            st.metric(
                "訓練ステップ",
                current.get("training_steps", 0)
            )
        
        with col4:
            trend = current.get("response_quality_trend", "stable")
            trend_emoji = {
                "improving": "📈",
                "stable": "➡️",
                "declining": "📉"
            }
            st.metric(
                "品質傾向",
                f"{trend_emoji.get(trend, '➡️')} {trend}"
            )
        
        st.divider()
        
        # グラフ表示
        timeseries = dashboard.get("timeseries", {})
        timestamps = timeseries.get("timestamps", [])
        ratings = timeseries.get("ratings", [])
        losses = timeseries.get("losses", [])
        improvements = timeseries.get("improvements", [])
        
        if timestamps:
            # 評価スコア推移
            fig_rating = go.Figure()
            fig_rating.add_trace(go.Scatter(
                x=timestamps,
                y=ratings,
                mode='lines+markers',
                name='Average Rating',
                line=dict(color='blue', width=2),
                fill='tozeroy'
            ))
            fig_rating.update_layout(
                title="📈 評価スコア推移",
                xaxis_title="時刻",
                yaxis_title="評価スコア",
                hovermode='x unified',
                height=400
            )
            st.plotly_chart(fig_rating, use_container_width=True)
            
            # 損失と改善率
            col1, col2 = st.columns(2)
            
            with col1:
                if losses:
                    fig_loss = go.Figure()
                    fig_loss.add_trace(go.Scatter(
                        x=timestamps,
                        y=losses,
                        mode='lines+markers',
                        name='Model Loss',
                        line=dict(color='red', width=2),
                        fill='tozeroy'
                    ))
                    fig_loss.update_layout(
                        title="📉 モデル損失",
                        xaxis_title="時刻",
                        yaxis_title="損失",
                        height=350
                    )
                    st.plotly_chart(fig_loss, use_container_width=True)
            
            with col2:
                if improvements:
                    fig_improve = go.Figure()
                    fig_improve.add_trace(go.Bar(
                        x=timestamps,
                        y=improvements,
                        name='Improvement %',
                        marker=dict(color='green')
                    ))
                    fig_improve.update_layout(
                        title="📊 改善率",
                        xaxis_title="時刻",
                        yaxis_title="改善率 (%)",
                        height=350
                    )
                    st.plotly_chart(fig_improve, use_container_width=True)
        
        st.divider()
        
        # 推奨アクション
        recommendations = dashboard.get("recommendations", [])
        if recommendations:
            st.subheader("💡 推奨アクション")
            for rec in recommendations:
                st.info(rec)
    
    @staticmethod
    def render_prompt_optimizer_ui(
        prompt_optimizer,
        feedback_manager,
    ):
        """プロンプト最適化UIをレンダリング"""
        st.subheader("🧠 プロンプト最適化")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("### 現在のテンプレート一覧")
            templates = prompt_optimizer.list_templates()
            
            if templates:
                df = pd.DataFrame(templates)
                st.dataframe(df, use_container_width=True)
            else:
                st.info("テンプレートがまだ登録されていません")
        
        with col2:
            st.write("### テンプレート管理")
            
            action = st.radio(
                "アクション選択",
                ["テンプレート追加", "最適化実行", "パフォーマンス表示"]
            )
            
            if action == "テンプレート追加":
                with st.form("new_template_form"):
                    name = st.text_input("テンプレート名", placeholder="my_template")
                    description = st.text_input("説明", placeholder="このテンプレートの用途")
                    system_prompt = st.text_area("システムプロンプト", height=100)
                    template = st.text_area(
                        "テンプレート（{context}, {query}を使用）",
                        height=100,
                        value="{context}\n\n質問: {query}\n\n答え:"
                    )
                    
                    if st.form_submit_button("保存"):
                        try:
                            prompt_optimizer.register_template(
                                name=name,
                                template=template,
                                system_prompt=system_prompt,
                                description=description,
                            )
                            st.success(f"テンプレート '{name}' を登録しました")
                        except Exception as e:
                            st.error(f"エラー: {e}")
            
            elif action == "最適化実行":
                st.write("フィードバックからテンプレートを最適化します")
                
                if st.button("最適化を実行"):
                    try:
                        feedback_items = feedback_manager.export_for_training(min_rating=0.0)
                        
                        if not feedback_items:
                            st.warning("最適化に必要なフィードバックがありません")
                        else:
                            result = prompt_optimizer.generate_optimized_template(
                                feedback_items,
                                low_rating_threshold=0.5
                            )
                            
                            if result:
                                st.success(
                                    f"新しい最適化テンプレート '{result.name}' を生成しました"
                                )
                                st.write(f"**説明**: {result.description}")
                            else:
                                st.info("最適化されたテンプレートを生成できませんでした")
                    
                    except Exception as e:
                        st.error(f"エラー: {e}")
            
            elif action == "パフォーマンス表示":
                templates = prompt_optimizer.templates
                
                if templates:
                    best = prompt_optimizer.get_best_template()
                    st.write(f"**最高性能**: {best.name}")
                    st.metric(
                        "平均評価",
                        f"{best.average_rating:.2%}",
                        f"成功率: {best.success_rate:.2%}"
                    )
                else:
                    st.info("テンプレートはまだ登録されていません")
    
    @staticmethod
    def render_training_status(continuous_trainer):
        """訓練ステータスをレンダリング"""
        st.subheader("🤖 マイクロファインチューニング状態")
        
        stats = continuous_trainer.get_training_stats()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("訓練ステップ", stats.get("total_steps", 0))
        with col2:
            st.metric("総サンプル数", stats.get("total_samples", 0))
        with col3:
            st.metric("平均損失", f"{stats.get('average_loss', 0):.4f}")
        with col4:
            st.metric("総改善率", f"{stats.get('total_improvement', 0):.1f}%")
        
        # 改善トレンド
        trend = continuous_trainer.get_improvement_trend(window=10)
        if trend:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                y=trend,
                mode='lines+markers',
                name='Improvement %',
                line=dict(color='green', width=2),
                fill='tozeroy'
            ))
            fig.update_layout(
                title="🔄 改善トレンド（最近10チェックポイント）",
                xaxis_title="チェックポイント",
                yaxis_title="改善率 (%)",
                height=350
            )
            st.plotly_chart(fig, use_container_width=True)
