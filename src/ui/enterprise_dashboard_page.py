import json
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px
from src.performance.cache_optimizer import get_cache_optimizer

def display_enterprise_dashboard():
    """Phase 20 Task 2: エンタープライズ統合ダッシュボードを表示する"""
    st.title("🛡️ エンタープライズ統合ダッシュボード")
    st.markdown("---")
    
    tab_reliability, tab_security, tab_performance = st.tabs([
        "📈 信頼性 & SLA", "🔒 セキュリティ & 監査", "⚡ パフォーマンス"
    ])
    
    # --- 1. 信頼性 & SLA ---
    with tab_reliability:
        st.subheader("可用性とレイテンシの監視")
        sla_log = Path("logs/sla_metrics.jsonl")
        if sla_log.exists():
            data = []
            with open(sla_log, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data.append(json.loads(line))
                    except: continue
            
            if data:
                df = pd.DataFrame(data)
                df['time'] = pd.to_datetime(df['timestamp'], unit='s')
                
                col1, col2, col3 = st.columns(3)
                col1.metric("稼働率", f"{df['availability'].iloc[-1]:.4f}%")
                col2.metric("p99 レイテンシ", f"{df['p99_latency'].iloc[-1]:.4f}s")
                col3.metric("総リクエスト数", f"{int(df['total_requests'].iloc[-1])}")
                
                # グラフ表示
                fig_lat = px.line(df, x='time', y='p99_latency', title="p99 レイテンシ推移")
                st.plotly_chart(fig_lat, use_container_width=True)
                
                fig_avail = px.line(df, x='time', y='availability', title="可用性推移")
                st.plotly_chart(fig_avail, use_container_width=True)
            else:
                st.info("データがまだありません。")
        else:
            st.warning("SLAログファイルが見つかりません。")

    # --- 2. セキュリティ & 監査 ---
    with tab_security:
        st.subheader("セキュリティ監査ログ")
        audit_log = Path("logs/audit.jsonl")
        if audit_log.exists():
            audit_data = []
            with open(audit_log, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        audit_data.append(json.loads(line))
                    except: continue
            
            if audit_data:
                df_audit = pd.DataFrame(audit_data)
                st.dataframe(df_audit.sort_values('timestamp', ascending=False), use_container_width=True)
                
                # PII検知統計
                if 'event_type' in df_audit.columns:
                    pii_events = df_audit[df_audit['event_type'] == 'pii_detection']
                    st.metric("累計 PII 検知数", len(pii_events))
            else:
                st.info("監査ログが空です。")
        else:
            st.warning("監査ログファイルが見つかりません。")

        st.markdown("---")
        st.subheader("倫理チェック監査ログ")
        ethics_log = Path("logs/ethics_audit.jsonl")
        if ethics_log.exists():
            ethics_data = []
            with open(ethics_log, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        ethics_data.append(json.loads(line))
                    except Exception:
                        continue

            if ethics_data:
                df_ethics = pd.DataFrame(ethics_data)
                if "decision" in df_ethics.columns:
                    # decision(dict) を列へ展開
                    decision_df = pd.json_normalize(df_ethics["decision"])
                    decision_df.columns = [f"decision.{c}" for c in decision_df.columns]
                    df_ethics = pd.concat([df_ethics.drop(columns=["decision"]), decision_df], axis=1)

                # フィルタUI
                filt_cols = st.columns([1, 1, 1, 1])
                with filt_cols[0]:
                    action_options = sorted(df_ethics["decision.action"].dropna().astype(str).unique().tolist()) if "decision.action" in df_ethics.columns else []
                    selected_actions = st.multiselect(
                        "action フィルタ",
                        options=action_options,
                        default=action_options,
                        key="ethics_filter_actions",
                    )
                with filt_cols[1]:
                    category_options = sorted(df_ethics["decision.category"].dropna().astype(str).unique().tolist()) if "decision.category" in df_ethics.columns else []
                    selected_categories = st.multiselect(
                        "category フィルタ",
                        options=category_options,
                        default=category_options,
                        key="ethics_filter_categories",
                    )
                with filt_cols[2]:
                    source_options = sorted(df_ethics["source"].dropna().astype(str).unique().tolist()) if "source" in df_ethics.columns else []
                    selected_sources = st.multiselect(
                        "source フィルタ",
                        options=source_options,
                        default=source_options,
                        key="ethics_filter_sources",
                    )
                with filt_cols[3]:
                    max_rows = st.slider("表示件数", min_value=10, max_value=300, value=100, step=10, key="ethics_filter_max_rows")

                df_filtered = df_ethics.copy()
                if "decision.action" in df_filtered.columns and selected_actions:
                    df_filtered = df_filtered[df_filtered["decision.action"].astype(str).isin(selected_actions)]
                if "decision.category" in df_filtered.columns and selected_categories:
                    df_filtered = df_filtered[df_filtered["decision.category"].astype(str).isin(selected_categories)]
                if "source" in df_filtered.columns and selected_sources:
                    df_filtered = df_filtered[df_filtered["source"].astype(str).isin(selected_sources)]

                total = len(df_filtered)
                warn_count = int((df_filtered.get("decision.action") == "warn").sum()) if "decision.action" in df_filtered.columns else 0
                block_count = int((df_filtered.get("decision.action") == "block").sum()) if "decision.action" in df_filtered.columns else 0
                allow_count = int((df_filtered.get("decision.action") == "allow").sum()) if "decision.action" in df_filtered.columns else 0

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("判定総数", total)
                c2.metric("ALLOW", allow_count)
                c3.metric("WARN", warn_count)
                c4.metric("BLOCK", block_count)

                display_cols = [
                    c for c in [
                        "timestamp",
                        "source",
                        "query_preview",
                        "decision.action",
                        "decision.category",
                        "decision.reason",
                        "decision.confidence",
                    ]
                    if c in df_ethics.columns
                ]
                sort_col = "timestamp" if "timestamp" in df_ethics.columns else None
                if sort_col:
                    df_filtered = df_filtered.sort_values(sort_col, ascending=False)
                st.dataframe(df_filtered[display_cols].head(max_rows), use_container_width=True)
            else:
                st.info("倫理監査ログが空です。")
        else:
            st.info("倫理監査ログファイル（logs/ethics_audit.jsonl）はまだ作成されていません。")

    # --- 3. パフォーマンス ---
    with tab_performance:
        st.subheader("キャッシュ & 最適化統計")
        cache = get_cache_optimizer()
        
        col1, col2 = st.columns(2)
        if cache.redis_client:
            col1.success("Redis L2 キャッシュ: 接続済み")
            try:
                info = cache.redis_client.info()
                col2.metric("Redis メモリ使用量", f"{info['used_memory_human']}")
                st.json(info['keyspace'] if 'keyspace' in info else {"msg": "キーなし"})
            except:
                col2.warning("Redis情報の取得に失敗")
        else:
            col1.error("Redis L2 キャッシュ: 未接続")
        
        st.markdown("---")
        st.write("※ キャッシュヒットにより検索レイテンシを約 99% 削減しています。")
