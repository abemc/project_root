"""
Learning Dashboard for Streamlit UI

This module provides interactive visualizations for Phase 5 learning systems.
Displays real-time statistics and learning progress of the AI agent.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import os
import json
import logging
from pathlib import Path
import uuid
import html
import streamlit.components.v1 as components

# Import Phase 5 manager
try:
    from src.rag.phase5_integration import get_phase5_manager, Phase5IntegrationManager
    PHASE5_AVAILABLE = True
except ImportError:
    PHASE5_AVAILABLE = False
    Phase5IntegrationManager = None

logger = logging.getLogger(__name__)

try:
    from src.self_improvement.integration import apply_reward_adjustments
    RLHF_GUARD_AVAILABLE = True
except Exception:
    RLHF_GUARD_AVAILABLE = False

try:
    from src.self_improvement.feedback_manager import FeedbackManager
    VALUE_TUNING_AVAILABLE = True
except Exception:
    VALUE_TUNING_AVAILABLE = False

try:
    from src.evaluation.regression_gate import RegressionGate
    REGRESSION_GATE_AVAILABLE = True
except Exception:
    RegressionGate = None
    REGRESSION_GATE_AVAILABLE = False

try:
    from src.evaluation.evaluation_diff_viewer import EvaluationDiffViewer
    EVALUATION_DIFF_AVAILABLE = True
except Exception:
    EvaluationDiffViewer = None
    EVALUATION_DIFF_AVAILABLE = False

try:
    from src.evaluation.trace_evidence_viewer import TraceEvidenceViewer
    TRACE_EVIDENCE_AVAILABLE = True
except Exception:
    TraceEvidenceViewer = None
    TRACE_EVIDENCE_AVAILABLE = False

try:
    from src.evaluation.failure_case_collector import FailureCaseCollector, FailureCategory
    FAILURE_CASE_AVAILABLE = True
except Exception:
    FAILURE_CASE_AVAILABLE = False

try:
    from src.evaluation.dataset_sanity_checker import DatasetSanityChecker, collect_issues_from_file
    DATASET_SANITY_AVAILABLE = True
except Exception:
    DATASET_SANITY_AVAILABLE = False

try:
    from src.evaluation.evaluation_diff_viewer import compute_diff_from_files, compute_diff
    EVAL_DIFF_AVAILABLE = True
except Exception:
    EVAL_DIFF_AVAILABLE = False


def _read_gate_logs(limit: int = 50) -> List[Dict[str, Any]]:
    """Read latest RLHF gate decisions from JSONL log."""
    log_path = os.path.join(os.getcwd(), "logs", "feedback", "rlhf_gate.jsonl")
    if not os.path.exists(log_path):
        return []

    records: List[Dict[str, Any]] = []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []

    return list(reversed(records[-limit:]))


def _build_gate_history_rows(logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build gate history rows with delta values versus the previous run."""
    rows: List[Dict[str, Any]] = []

    for idx, item in enumerate(logs):
        summary = item.get("summary") or {}
        prev_summary = (logs[idx + 1].get("summary") or {}) if idx + 1 < len(logs) else {}

        entries = summary.get("total_entries") if isinstance(summary.get("total_entries"), (int, float)) else None
        csat = summary.get("csat_mean") if isinstance(summary.get("csat_mean"), (int, float)) else None
        nps = summary.get("nps_mean") if isinstance(summary.get("nps_mean"), (int, float)) else None
        adoption = summary.get("adoption_rate") if isinstance(summary.get("adoption_rate"), (int, float)) else None

        prev_entries = prev_summary.get("total_entries") if isinstance(prev_summary.get("total_entries"), (int, float)) else None
        prev_csat = prev_summary.get("csat_mean") if isinstance(prev_summary.get("csat_mean"), (int, float)) else None
        prev_nps = prev_summary.get("nps_mean") if isinstance(prev_summary.get("nps_mean"), (int, float)) else None
        prev_adoption = prev_summary.get("adoption_rate") if isinstance(prev_summary.get("adoption_rate"), (int, float)) else None

        rows.append(
            {
                "timestamp": item.get("timestamp", ""),
                "status": item.get("status", ""),
                "source": item.get("source", "human_only"),
                "reasons": ", ".join(item.get("reasons") or []),
                "entries": entries,
                "csat": csat,
                "nps": nps,
                "adoption": adoption,
                "Δentries": None if entries is None or prev_entries is None else entries - prev_entries,
                "Δcsat": None if csat is None or prev_csat is None else csat - prev_csat,
                "Δnps": None if nps is None or prev_nps is None else nps - prev_nps,
                "Δadoption": None if adoption is None or prev_adoption is None else adoption - prev_adoption,
            }
        )

    return rows


def _format_gate_history_rows(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    """Format gate history rows for display in Streamlit."""
    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(rows)

    def _format_number(value: Any) -> Any:
        if isinstance(value, (int, float)):
            return f"{value:.2f}"
        return value

    def _format_delta(value: Any) -> Any:
        if value is None or not isinstance(value, (int, float)):
            return None
        if value > 0:
            return f"↑ {value:+.2f}"
        if value < 0:
            return f"↓ {value:+.2f}"
        return "→ +0.00"

    for column in ["csat", "nps", "adoption"]:
        if column in frame.columns:
            frame[column] = frame[column].apply(_format_number)

    for column in ["Δentries", "Δcsat", "Δnps", "Δadoption"]:
        if column in frame.columns:
            frame[column] = frame[column].apply(_format_delta)

    return frame


def _style_gate_history_rows(frame: pd.DataFrame):
    """Apply emphasis to delta columns in the gate history table."""
    if frame.empty:
        return frame.style

    def _is_strong_delta(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        try:
            parts = value.split()
            if len(parts) < 2:
                return False
            return abs(float(parts[1])) >= 0.10
        except Exception:
            return False

    def _delta_style(value: Any) -> str:
        if isinstance(value, str) and value.startswith("↑"):
            base = "background-color: #e8f5e9; color: #1b5e20; font-weight: 600;"
            return base + " font-weight: 700;" if _is_strong_delta(value) else base
        if isinstance(value, str) and value.startswith("↓"):
            base = "background-color: #ffebee; color: #b71c1c; font-weight: 600;"
            return base + " font-weight: 700;" if _is_strong_delta(value) else base
        if value == "→ +0.00":
            return "background-color: #f5f5f5; color: #616161;"
        return ""

    try:
        style_obj = frame.style
        subset_cols = [col for col in ["Δcsat", "Δnps", "Δadoption"] if col in frame.columns]
        if hasattr(style_obj, "map"):
            return style_obj.map(_delta_style, subset=subset_cols)
        elif hasattr(style_obj, "applymap"):
            return style_obj.applymap(_delta_style, subset=subset_cols)
        return style_obj
    except Exception:
        return frame.style


def _find_recent_benchmark_results(limit: int = 2) -> List[str]:
    """Find recent benchmark-like result files under results/benchmarks."""
    base_dir = os.path.join(os.getcwd(), "results", "benchmarks")
    if not os.path.isdir(base_dir):
        return []

    candidates: List[str] = []
    for entry in os.scandir(base_dir):
        if not entry.is_file() or not entry.name.endswith(".json"):
            continue
        if not (
            entry.name.startswith("benchmark_results")
            or entry.name.startswith("benchmark")
            or entry.name.startswith("results")
            or entry.name.startswith("rag_evaluation_")
        ):
            continue
        candidates.append(entry.path)

    candidates.sort(key=lambda path: os.path.getmtime(path), reverse=True)
    return candidates[:limit]


def _read_regression_gate_reports(limit: int = 30) -> List[Dict[str, Any]]:
    """Read saved regression gate reports from results/benchmarks."""
    base_dir = os.path.join(os.getcwd(), "results", "benchmarks")
    if not os.path.isdir(base_dir):
        return []

    candidates: List[str] = []
    for entry in os.scandir(base_dir):
        if entry.is_file() and entry.name.startswith("regression_gate_") and entry.name.endswith(".json"):
            candidates.append(entry.path)

    candidates.sort(key=lambda path: os.path.getmtime(path), reverse=True)

    records: List[Dict[str, Any]] = []
    for path in candidates[:limit]:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                record = json.load(handle)
                record["_path"] = path
                records.append(record)
        except Exception:
            continue

    return records


def _format_regression_gate_rows(records: List[Dict[str, Any]]) -> pd.DataFrame:
    """Format saved regression gate reports for display."""
    if not records:
        return pd.DataFrame()

    rows: List[Dict[str, Any]] = []
    for record in records:
        summary = record.get("summary") or {}
        rows.append(
            {
                "timestamp": record.get("current_timestamp", ""),
                "status": record.get("status", ""),
                "comparable": summary.get("comparable_benchmarks", 0),
                "regressed": summary.get("regressed_benchmarks", 0),
                "improved": summary.get("improved_benchmarks", 0),
                "notes": "; ".join(record.get("notes") or []),
                "path": os.path.basename(record.get("_path", "")),
            }
        )

    return pd.DataFrame(rows)


def _read_rag_evaluation_reports(limit: int = 30) -> List[Dict[str, Any]]:
    """Read saved RAG evaluation reports from results/benchmarks."""
    base_dir = os.path.join(os.getcwd(), "results", "benchmarks")
    if not os.path.isdir(base_dir):
        return []

    candidates: List[str] = []
    for entry in os.scandir(base_dir):
        if entry.is_file() and entry.name.startswith("rag_evaluation_") and entry.name.endswith(".json"):
            candidates.append(entry.path)

    candidates.sort(key=lambda path: os.path.getmtime(path), reverse=True)

    records: List[Dict[str, Any]] = []
    for path in candidates[:limit]:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                record = json.load(handle)
                record["_path"] = path
                records.append(record)
        except Exception:
            continue

    return records


def _format_rag_evaluation_rows(records: List[Dict[str, Any]]) -> pd.DataFrame:
    """Format saved RAG evaluation reports for display."""
    if not records:
        return pd.DataFrame()

    rows: List[Dict[str, Any]] = []
    for record in records:
        summary = record.get("summary") or {}
        average_metrics = summary.get("average_metrics") or {}
        results = record.get("results") or []
        sample_count = summary.get("total_samples")
        if sample_count is None and results:
            sample_count = results[0].get("num_samples", 0)
        rows.append(
            {
                "timestamp": record.get("timestamp", ""),
                "samples": sample_count or 0,
                "end_to_end": average_metrics.get("end_to_end_score", 0.0),
                "factual_consistency": average_metrics.get("factual_consistency", 0.0),
                "rouge": average_metrics.get("rouge", 0.0),
                "bleu": average_metrics.get("bleu", 0.0),
                "path": os.path.basename(record.get("_path", "")),
            }
        )

    return pd.DataFrame(rows)


def _format_evaluation_diff_rows(report: Any) -> pd.DataFrame:
    """Format sample-level diff report for Streamlit display."""
    sample_diffs = getattr(report, "sample_diffs", None) or []
    if not sample_diffs:
        return pd.DataFrame()

    rows: List[Dict[str, Any]] = []
    for item in sample_diffs:
        status = getattr(item, "status", "")
        if status not in {"improved", "regressed"}:
            continue

        rows.append(
            {
                "status": status,
                "query": getattr(item, "query", "") or getattr(item, "sample_key", ""),
                "Δend_to_end": getattr(item, "delta_end_to_end", None),
                "Δfactual": getattr(item, "delta_factual_consistency", None),
                "Δrouge": getattr(item, "delta_rouge", None),
                "Δbleu": getattr(item, "delta_bleu", None),
            }
        )

    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(rows)
    frame["abs_delta"] = (
        frame["Δend_to_end"].fillna(0.0).abs()
        + frame["Δfactual"].fillna(0.0).abs()
        + frame["Δrouge"].fillna(0.0).abs()
        + frame["Δbleu"].fillna(0.0).abs()
    )
    frame = frame.sort_values(["status", "abs_delta"], ascending=[True, False])
    return frame.drop(columns=["abs_delta"])


def report_to_csv_bytes(report: Dict[str, Any]) -> bytes:
    """Convert evaluation diff report items to CSV bytes."""
    import csv
    import io
    items = report.get("items") or []
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "type", "baseline_score", "current_score", "delta"])
    for r in items:
        writer.writerow([r.get("id"), r.get("type"), r.get("baseline_score"), r.get("current_score"), r.get("delta")])
    return output.getvalue().encode("utf-8")


class LearningDashboard:
    """Interactive dashboard for Phase 5 learning systems."""
    
    def __init__(self, manager: Optional['Phase5IntegrationManager'] = None):
        """
        Initialize the dashboard.
        
        Args:
            manager: Phase5IntegrationManager instance (optional)
        """
        self.manager = manager or (get_phase5_manager() if PHASE5_AVAILABLE else None)
    
    def render(self):
        """Render the complete learning dashboard."""
        if not self.manager:
            st.warning("⚠️ Phase 5 Learning Systems are not available")
            return
        
        st.markdown("---")
        st.header("🧠 AI Learning Dashboard")
        
        # Create tabs for different views
        tabs = st.tabs([
            "📊 Statistics",
            "🤖 RAG & CRAG モニター",
            "🔄 Transfer Learning",
            "🎲 Reinforcement Learning",
            "💾 Memory Management",
            "❌ Failure Cases",
            "🧾 Dataset Sanity",
            "🔍 Eval Diffs",
            "🤖 Model Architecture",
        ])
        tab1, tab_rag, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = tabs
        
        with tab1:
            self._render_statistics()

        with tab_rag:
            self._render_rag_crag_monitor()
        
        with tab2:
            self._render_transfer_learning()
        
        with tab3:
            self._render_reinforcement_learning()
        
        with tab4:
            self._render_memory_management()
        
        with tab5:
            self._render_failure_cases()
        
        with tab6:
            self._render_dataset_sanity()

        with tab7:
            self._render_evaluation_diffs()

        with tab8:
            self._render_model_architecture()

    def _render_rag_crag_monitor(self):
        """Render RAG & CRAG performance monitor."""
        st.subheader("🤖 RAG & CRAG パフォーマンスモニター")
        st.markdown(
            "自律型 RAG エージェントのゲート閾値、状態遷移トレース、および外部検索（Corrective RAG）の動作状況を可視化します。"
        )

        # 1. 閾値の設定・確認 (スライダー)
        try:
            from rag_agent_config import RAGAgentConfig
            config_manager = RAGAgentConfig()
            current_config = config_manager.load_config()
        except Exception:
            current_config = {}

        # ゲート閾値の設定（confidence_threshold または crag_confidence_threshold）
        current_threshold = current_config.get("confidence_threshold", 0.45)
        
        col_conf, col_save = st.columns([3, 1])
        with col_conf:
            new_threshold = st.slider(
                "🎯 CRAG 外部検索ゲート閾値 (スライダーを変更して保存できます)",
                min_value=0.0,
                max_value=1.0,
                value=float(current_threshold),
                step=0.05,
                help="ローカル検索の確信度スコアがこの閾値未満の場合、外部検索 (CRAG) を実行します。",
                key="dashboard_crag_threshold_slider"
            )
        with col_save:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if st.button("💾 閾値を保存", key="save_dashboard_crag_threshold", use_container_width=True):
                current_config["confidence_threshold"] = new_threshold
                current_config["crag_confidence_threshold"] = new_threshold # 同期して両方保存
                try:
                    config_manager.save_config(current_config)
                    st.success("✅ 保存完了")
                    st.rerun()
                except Exception as e:
                    st.error(f"保存失敗: {e}")

        # 2. ログデータの読み込み
        log_file = Path(__file__).resolve().parent.parent.parent / "logs" / "agent_responses.jsonl"
        logs = []
        if log_file.exists():
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            logs.append(json.loads(line))
            except Exception as e:
                st.warning(f"ログファイル読み込みエラー: {e}")

        # デモデータ切り替え用のトグル
        use_demo = False
        if not logs:
            st.info("ℹ️ 現在、実際のクエリ実行ログが存在しません。デモデータを表示しています。")
            use_demo = True
        else:
            use_demo = st.checkbox("🧪 デモデータを表示（シミュレーション用）", value=False)

        if use_demo:
            # 仮想デモデータを作成
            logs = [
                {
                    "timestamp": (datetime.now() - timedelta(minutes=i*15)).isoformat(),
                    "question": f"デモ質問 {i}",
                    "confidence": round(0.1 + (i % 7) * 0.13, 2),
                    "execution_trace": [
                        {"step": 1, "action": "search_corpus", "result": "confidence=" + str(round(0.1 + (i % 7) * 0.13, 2))},
                        {"step": 2, "action": "web_corrective_search", "result": "web_hits=3"} if (0.1 + (i % 7) * 0.13) < new_threshold else None,
                        {"step": 3, "action": "generate_answer", "result": "llm"},
                        {"step": 4, "action": "ethics_audit", "result": "pass"},
                        {"step": 5, "action": "risk_gate", "result": "passed"}
                    ],
                    "ethics_audit": {"overall_score": 0.85 + (i % 3) * 0.05, "status": "pass"},
                    "risk_assessment": {"risk_score": 0.1 + (i % 5) * 0.05, "risk_level": "low"}
                }
                for i in range(1, 41)
            ]
            # Noneを除去
            for log in logs:
                log["execution_trace"] = [t for t in log["execution_trace"] if t is not None]

        # 3. データの集計と可視化
        if logs:
            df_rows = []
            for item in logs:
                # ログのキー構造を標準化
                q = item.get("question", "N/A")
                ts = item.get("timestamp", "")
                
                resp_obj = item.get("response")
                if not isinstance(resp_obj, dict):
                    resp_obj = {}

                # confidence のパース
                conf = item.get("confidence")
                if conf is None:
                    # 応答自体が入れ子になっている場合のフォールバック
                    conf = resp_obj.get("confidence", 0.5)
                
                # web検索があったかどうかの判定 (traceから)
                trace = item.get("execution_trace") or resp_obj.get("execution_trace", [])
                web_searched = False
                if isinstance(trace, list):
                    for t in trace:
                        if isinstance(t, dict) and t.get("action") == "web_corrective_search" and t.get("result") != "unavailable":
                            web_searched = True
                            break

                # 倫理監査
                ethics = item.get("ethics_audit") or resp_obj.get("ethics_audit", {})
                if not isinstance(ethics, dict):
                    ethics = {}
                ethics_score = ethics.get("overall_score") or 0.85
                ethics_status = ethics.get("status") or "pass"

                # リスク
                risk = item.get("risk_assessment") or resp_obj.get("risk_assessment", {})
                if not isinstance(risk, dict):
                    risk = {}
                risk_score = risk.get("risk_score") or 0.1
                risk_level = risk.get("risk_level") or "low"

                df_rows.append({
                    "日時": ts.split("T")[0] + " " + ts.split("T")[1][:5] if "T" in ts else ts,
                    "質問": q,
                    "信頼度": float(conf),
                    "Web検索 (CRAG)": "実行 (Web)" if web_searched else "未実行 (ローカル)",
                    "倫理スコア": float(ethics_score),
                    "倫理判定": ethics_status,
                    "リスクスコア": float(risk_score),
                    "リスクレベル": risk_level,
                    "トレース": trace
                })

            df = pd.DataFrame(df_rows)

            # 指標カード
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            with m_col1:
                st.metric("総対話件数", len(df))
            with m_col2:
                avg_conf = df["信頼度"].mean()
                st.metric("平均信頼度", f"{avg_conf:.2f}")
            with m_col3:
                crag_runs = df["Web検索 (CRAG)"].value_counts().get("実行 (Web)", 0)
                crag_rate = crag_runs / len(df) if len(df) > 0 else 0.0
                st.metric("CRAG 発生率 (外部検索率)", f"{crag_rate:.1%}")
            with m_col4:
                blocked_runs = df[df["倫理判定"] == "fail"].shape[0]
                block_rate = blocked_runs / len(df) if len(df) > 0 else 0.0
                st.metric("安全ブロック率", f"{block_rate:.1%}")

            # グラフ表示
            g_col1, g_col2 = st.columns(2)
            with g_col1:
                st.write("**📊 CRAG 迂回ルーティング比率**")
                pie_df = df["Web検索 (CRAG)"].value_counts().reset_index()
                pie_df.columns = ["ルーティング", "件数"]
                fig_pie = px.pie(
                    pie_df,
                    values="件数",
                    names="ルーティング",
                    color="ルーティング",
                    color_discrete_map={"未実行 (ローカル)": "#0284c7", "実行 (Web)": "#f97316"},
                    hole=0.4
                )
                fig_pie.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=280)
                st.plotly_chart(fig_pie, use_container_width=True)

            with g_col2:
                st.write("**📈 確信度の分布とゲート閾値**")
                fig_hist = px.histogram(
                    df,
                    x="信頼度",
                    nbins=10,
                    labels={"信頼度": "信頼度スコア"},
                    color_discrete_sequence=["#38bdf8"]
                )
                # 閾値境界線の追加
                fig_hist.add_vline(
                    x=new_threshold,
                    line_width=3,
                    line_dash="dash",
                    line_color="red",
                    annotation_text=f"ゲート閾値 ({new_threshold:.2f})",
                    annotation_position="top left"
                )
                fig_hist.update_layout(
                    margin=dict(t=20, b=20, l=10, r=10),
                    height=280,
                    xaxis_range=[0.0, 1.05],
                    yaxis_title="クエリ件数"
                )
                st.plotly_chart(fig_hist, use_container_width=True)

            # トランザクション履歴 ＆ トレース詳細
            st.subheader("🔍 デバッグ実行トレース詳細")
            st.markdown("対話ログを選択すると、どのような状態遷移（Graphノード）をたどって回答が生成されたかを確認できます。")

            # セレクトボックスで質問を選択
            q_options = [f"[{row['日時']}] {row['質問'][:40]}..." for _, row in df.iterrows()]
            selected_q_idx = st.selectbox("確認する対話ログを選択してください", range(len(q_options)), format_func=lambda x: q_options[x], key="dashboard_log_select")

            if selected_q_idx is not None:
                selected_row = df.iloc[selected_q_idx]
                st.info(f"**選択された質問:** {selected_row['質問']}")
                
                # トレースの可視化
                st.markdown("**状態遷移プロセス (Trace Timeline):**")
                trace_list = selected_row["トレース"]
                if trace_list:
                    timeline_html = []
                    for idx, step in enumerate(trace_list, 1):
                        action = step.get("action")
                        result = step.get("result")
                        
                        # アクション名とアイコンの定義
                        icon = "🟢"
                        action_ja = action
                        if action == "search_corpus":
                            icon = "🔍"
                            action_ja = "ローカルナレッジ検索 (Retrieve)"
                        elif action == "web_corrective_search":
                            icon = "🌐"
                            action_ja = "外部Web検索 (CRAG)"
                        elif action == "generate_answer":
                            icon = "✍️"
                            action_ja = "回答合成 (Generate)"
                        elif action == "ethics_audit":
                            icon = "🛡️"
                            action_ja = "倫理監査 (Audit)"
                        elif action == "risk_gate":
                            icon = "🚨"
                            action_ja = "リスクゲート評価 (Risk Gate)"

                        # デザインの構築
                        timeline_html.append(
                            f"<div style='padding: 10px; margin-bottom: 8px; border-left: 4px solid #0284c7; background-color: #f0f9ff; border-radius: 0 8px 8px 0;'>"
                            f"<strong>ステップ {idx}: {icon} {action_ja}</strong><br>"
                            f"<span style='color: #475569; font-size: 0.9em;'>結果/ステータス: {result}</span>"
                            f"</div>"
                        )
                    st.markdown("\n".join(timeline_html), unsafe_allow_html=True)
                else:
                    st.warning("⚠️ この対話には詳細な実行トレースが記録されていません。")

                # 監査詳細
                aud_col1, aud_col2 = st.columns(2)
                with aud_col1:
                    st.markdown("**🛡️ 倫理監査結果:**")
                    st.write(f"・判定: `{selected_row['倫理判定']}`")
                    st.write(f"・監査スコア: `{selected_row['倫理スコア']:.3f}`")
                with aud_col2:
                    st.markdown("**🚨 リスク判定:**")
                    st.write(f"・リスクレベル: `{selected_row['リスクレベル']}`")
                    st.write(f"・リスクスコア: `{selected_row['リスクスコア']:.3f}`")
        else:
            st.info("📭 実行履歴がありません。一度RAGエージェントと会話すると、ログが蓄積されます。")
    
    def _render_statistics(self):
        """Render execution statistics."""
        st.subheader("📈 Execution Statistics")
        
        stats = self.manager.get_learning_statistics()
        
        # Create metrics columns
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="Total Executions",
                value=stats["total_executions"],
                delta=None,
                help="Total number of executed tasks"
            )
        
        with col2:
            st.metric(
                label="Success Rate",
                value=f"{stats['success_rate']:.1%}",
                delta=None,
                help="Percentage of successful executions"
            )
        
        with col3:
            st.metric(
                label="Average Quality",
                value=f"{stats['average_quality']:.2f}",
                delta=None,
                help="Average output quality (0-1)"
            )
        
        with col4:
            st.metric(
                label="Active Systems",
                value=stats["systems_active"],
                delta=None,
                help="Number of learning systems active"
            )

        # Show last learning time and agents involved
        if self.manager.execution_traces:
            last_ts = max((t.timestamp for t in self.manager.execution_traces))
            agents = sorted(set(t.agent_id for t in self.manager.execution_traces if getattr(t, 'agent_id', None)))
        else:
            last_ts = None
            agents = []

        col5, col6 = st.columns(2)
        with col5:
            st.metric(label="Last Learned", value=last_ts.strftime('%Y-%m-%d %H:%M:%S') if last_ts else "-")
        with col6:
            st.write("**Agents:** " + (", ".join(agents) if agents else "-"))
        
        # Execution timeline
        if self.manager.execution_traces:
            st.subheader("⏱️ Execution Timeline")
            
            # Convert traces to dataframe
            traces_data = []
            for trace in self.manager.execution_traces[-20:]:  # Last 20
                traces_data.append({
                    "Time": trace.timestamp,
                    "Task": trace.task_family[:40],
                    "Agent": getattr(trace, 'agent_id', 'unknown'),
                    "Input": (getattr(trace, 'input_query', '') or '')[:200],
                    "Error": getattr(trace, 'error_message', '') or '',
                    "Success": "✅" if trace.success else "❌",
                    "Quality": trace.output_quality,
                    "Duration (ms)": trace.execution_time_ms,
                })
            
            if traces_data:
                df = pd.DataFrame(traces_data)
                st.dataframe(df, use_container_width=True)
        
        # Distribution charts
        if self.manager.execution_traces:
            col1, col2 = st.columns(2)
            
            with col1:
                # Success distribution
                success_count = len([t for t in self.manager.execution_traces if t.success])
                fail_count = len(self.manager.execution_traces) - success_count
                
                fig = go.Figure(data=[
                    go.Pie(
                        labels=["Success", "Failed"],
                        values=[success_count, fail_count],
                        marker=dict(colors=["#2ecc71", "#e74c3c"]),
                    )
                ])
                fig.update_layout(title="Success Distribution", height=300)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Quality distribution
                qualities = [t.output_quality for t in self.manager.execution_traces]
                
                fig = px.histogram(
                    x=qualities,
                    nbins=10,
                    title="Quality Score Distribution",
                    labels={"x": "Quality Score", "y": "Count"},
                    color_discrete_sequence=["#3498db"]
                )
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)
    
    def _render_transfer_learning(self):
        """Render Transfer Learning statistics."""
        st.subheader("🔄 Transfer Learning")
        
        st.write("""
        Transfer Learning enables knowledge sharing across similar tasks,
        accelerating learning on new tasks by up to 30-50%.
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric(
                label="Task Families Known",
                value=8,
                help="Number of task family categories"
            )
        
        with col2:
            st.metric(
                label="Knowledge Transfers",
                value=len([t for t in self.manager.execution_traces if len(t.tools_used) > 0]),
                help="Number of knowledge transfer attempts"
            )
        
        # Task family information
        st.write("**Task Families:**")
        families = [
            "📊 Data Analysis",
            "📝 Text Processing",
            "🖥️ System Admin",
            "🌐 API Integration",
            "🗄️ Database Operations",
            "📈 Visualization",
            "🤖 ML Training",
        ]
        
        for family in families:
            st.write(f"- {family}")
    
    def _render_reinforcement_learning(self):
        """Render Reinforcement Learning dashboard."""
        st.subheader("🎲 Reinforcement Learning")
        
        st.write("""
        Reinforcement Learning optimizes decisions through reward signals,
        improving strategy effectiveness by 20-40% over time.
        """)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                label="Decisions Recorded",
                value=len(self.manager.rl_manager.decisions),
                help="Total number of decisions recorded"
            )
        
        with col2:
            st.metric(
                label="Policies Learned",
                value=len(self.manager.rl_manager.policies),
                help="Number of learned policies"
            )
        
        with col3:
            st.metric(
                label="Experience Replay Size",
                value=len(self.manager.rl_manager.experience_replay),
                help="Stored experiences for learning"
            )
        
        # Reward signals
        st.write("**Active Reward Signals:**")
        reward_signals = [
            "✅ Task Success",
            "⚡ Execution Time",
            "⭐ Output Quality",
            "💾 Resource Efficiency",
            "📚 Learning Gain",
            "🛡️ Error Avoidance",
            "😊 User Satisfaction",
        ]
        
        from src.self_improvement.reinforcement_learning import RewardSignal
        signal_mapping = {
            "✅ Task Success": RewardSignal.TASK_SUCCESS,
            "⚡ Execution Time": RewardSignal.EXECUTION_TIME,
            "⭐ Output Quality": RewardSignal.QUALITY,
            "💾 Resource Efficiency": RewardSignal.RESOURCE_EFFICIENCY,
            "📚 Learning Gain": RewardSignal.LEARNING_GAIN,
            "🛡️ Error Avoidance": RewardSignal.ERROR_AVOIDANCE,
            "😊 User Satisfaction": RewardSignal.USER_SATISFACTION,
        }
        
        weights = getattr(self.manager.rl_manager, "reward_weights", {})
        for i, signal in enumerate(reward_signals, 1):
            enum_key = signal_mapping.get(signal)
            weight_val = weights.get(enum_key, 0.0) if enum_key else 0.0
            st.write(f"{i}. {signal} (Weight: **{weight_val:.2f}**)")

        st.divider()
        st.subheader("🎯 Value Tuning")

        if not VALUE_TUNING_AVAILABLE:
            st.caption("Value Tuningモジュールが利用できません。")
        else:
            try:
                feedback_manager = FeedbackManager()
                value_summary = feedback_manager.get_value_tuning_summary(min_rating=0.0)
                value_timeseries = feedback_manager.get_value_tuning_timeseries(min_rating=0.0)
                recent_feedback = feedback_manager.get_recent_feedback(n=1)
            except Exception:
                value_summary = {}
                value_timeseries = {}
                recent_feedback = []

            signal_means = value_summary.get("signal_means") or {}
            signal_counts = value_summary.get("signal_counts") or {}
            total_items = int(value_summary.get("total_items") or 0)
            latest_feedback_at = recent_feedback[-1].timestamp if recent_feedback else None

            info_col1, info_col2 = st.columns(2)
            with info_col1:
                st.metric("Feedback Items", total_items)
            with info_col2:
                st.metric("Latest Feedback", latest_feedback_at or "-")

            if recent_feedback:
                latest = recent_feedback[-1]
                query = getattr(latest, "user_query", "") or getattr(latest, "query", "") or "-"
                rating = getattr(latest, "rating", None)
                tags = getattr(latest, "tags", None) or []
                rating_text = f"{float(rating):.2f}" if isinstance(rating, (int, float)) else "-"
                tag_text = ", ".join(tags) if tags else "-"
                
                # Display latest feedback in detail card format
                st.divider()
                st.subheader("最新フィードバック詳細")
                
                latest_detail_col1, latest_detail_col2, latest_detail_col3 = st.columns(3)
                with latest_detail_col1:
                    st.write("**Query**")
                    st.caption(query if len(query) <= 60 else query[:60] + "...")
                
                with latest_detail_col2:
                    st.write("**Rating**")
                    # Use color-coded rating display
                    if isinstance(rating, (int, float)):
                        rating_float = float(rating)
                        if rating_float >= 0.8:
                            st.success(f"⭐ {rating_text}")
                        elif rating_float >= 0.6:
                            st.info(f"👍 {rating_text}")
                        else:
                            st.warning(f"👎 {rating_text}")
                    else:
                        st.caption("-")
                
                with latest_detail_col3:
                    st.write("**Tags**")
                    if tags:
                        for tag in tags:
                            st.caption(f"🏷️ {tag}")
                    else:
                        st.caption("-")

            if not signal_means:
                st.caption("価値軸シグナルはまだありません。フィードバックタグやコメントが蓄積されると表示されます。")
            else:
                st.write("**価値軸ごとの平均スコアと評価件数**")
                
                # Plotly radar chart
                dimensions = ["accuracy", "clarity", "helpfulness", "safety", "transparency", "neutrality"]
                radar_labels = ["正確性 (accuracy)", "明瞭性 (clarity)", "有用性 (helpfulness)", "安全性 (safety)", "透明性 (transparency)", "中立性 (neutrality)"]
                scores = [float(signal_means.get(d, 0.0)) for d in dimensions]
                
                # Radar chart requires closing the loop by adding the first element to the end
                r_scores = scores + [scores[0]]
                theta_labels = radar_labels + [radar_labels[0]]
                
                fig_radar = go.Figure()
                fig_radar.add_trace(go.Scatterpolar(
                    r=r_scores,
                    theta=theta_labels,
                    fill='toself',
                    fillcolor='rgba(52, 152, 219, 0.2)',
                    line=dict(color='#3498db', width=2),
                    name='Value Alignment'
                ))
                fig_radar.update_layout(
                    polar=dict(
                        radialaxis=dict(
                            visible=True,
                            range=[0, 1]
                        )
                    ),
                    showlegend=False,
                    height=350,
                    margin=dict(l=40, r=40, t=20, b=20)
                )
                
                col_chart, col_details = st.columns([1.2, 1.0])
                with col_chart:
                    st.plotly_chart(fig_radar, use_container_width=True)
                
                with col_details:
                    st.write("**現在の価値評価スコア**")
                    for d_key, label in zip(dimensions, radar_labels):
                        score = float(signal_means.get(d_key, 0.0))
                        count = int(signal_counts.get(d_key, 0))
                        
                        st.caption(f"{label}: **{score:.2f}** ({count} 件)")
                        st.progress(score)

                top_key = max(signal_means, key=signal_means.get)
                st.caption(f"現在最も強い価値軸: {top_key} ({signal_means[top_key]:.2f})")

                timestamps = value_timeseries.get("timestamps") or []
                signal_series = value_timeseries.get("signals") or {}
                safety_values = signal_series.get("safety") or []
                if timestamps and any(v is not None for v in safety_values):
                    trend_df = pd.DataFrame(
                        {
                            "timestamp": pd.to_datetime(timestamps),
                            "safety": safety_values,
                            "accuracy": signal_series.get("accuracy") or [None] * len(timestamps),
                            "clarity": signal_series.get("clarity") or [None] * len(timestamps),
                        }
                    )
                    fig_value = go.Figure()
                    fig_value.add_trace(go.Scatter(
                        x=trend_df["timestamp"],
                        y=trend_df["safety"],
                        mode="lines+markers",
                        name="safety",
                        line=dict(color="#e67e22", width=3),
                    ))
                    fig_value.add_trace(go.Scatter(
                        x=trend_df["timestamp"],
                        y=trend_df["accuracy"],
                        mode="lines",
                        name="accuracy",
                        line=dict(color="#3498db", width=2, dash="dot"),
                    ))
                    fig_value.add_trace(go.Scatter(
                        x=trend_df["timestamp"],
                        y=trend_df["clarity"],
                        mode="lines",
                        name="clarity",
                        line=dict(color="#2ecc71", width=2, dash="dash"),
                    ))
                    fig_value.update_layout(
                        title="Value Tuning 時系列（rolling average）",
                        xaxis_title="timestamp",
                        yaxis_title="signal score",
                        yaxis=dict(range=[0, 1]),
                        height=340,
                        hovermode="x unified",
                    )
                    st.plotly_chart(fig_value, use_container_width=True)
                    st.caption(
                        f"safety を中心に accuracy / clarity を重ねて表示しています。window={value_timeseries.get('rolling_window', 0)}"
                    )

        st.divider()
        st.subheader("🛡️ RLHF/RLAIF適用ガードレール")

        if not RLHF_GUARD_AVAILABLE:
            st.info("RLHFガードレールモジュールが利用できません。")
            return

        default_min_entries = int(st.session_state.get("rlhf_gate_min_entries", 20))
        default_min_csat = float(st.session_state.get("rlhf_gate_min_csat", 3.2))
        default_min_adoption = float(st.session_state.get("rlhf_gate_min_adoption_rate", 0.30))
        default_min_nps = float(st.session_state.get("rlhf_gate_min_nps", 0.0))
        default_ai_weight = float(st.session_state.get("rlaif_ai_weight", 0.35))
        default_min_ai_entries = int(st.session_state.get("rlaif_min_ai_entries", 30))
        default_min_ai_confidence = float(st.session_state.get("rlaif_min_ai_confidence", 0.60))
        default_auto_aggregate_ai = bool(st.session_state.get("rlaif_auto_aggregate_ai", True))
        default_enable_delta_cap = bool(st.session_state.get("rlaif_enable_delta_cap", True))
        default_max_weight_delta = float(st.session_state.get("rlaif_max_weight_delta", 0.25))
        default_value_tuning_bias_enabled = bool(st.session_state.get("value_tuning_bias_enabled", True))
        default_value_tuning_min_items = int(st.session_state.get("value_tuning_min_items", 5))
        default_value_tuning_max_bias = float(st.session_state.get("value_tuning_max_bias", 0.12))

        st.caption("現在の閾値（サイドバーで調整可能）")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("min_entries", default_min_entries)
        with c2:
            st.metric("min_csat", f"{default_min_csat:.2f}")
        with c3:
            st.metric("min_adoption", f"{default_min_adoption:.2f}")
        with c4:
            st.metric("min_nps", f"{default_min_nps:.2f}")

        d1, d2, d3 = st.columns(3)
        with d1:
            st.metric("ai_weight", f"{default_ai_weight:.2f}")
        with d2:
            st.metric("min_ai_entries", default_min_ai_entries)
        with d3:
            st.metric("min_ai_conf", f"{default_min_ai_confidence:.2f}")

        st.caption(f"auto_ai_aggregate: {'on' if default_auto_aggregate_ai else 'off'}")
        st.caption(f"rlaif_delta_cap: {'on' if default_enable_delta_cap else 'off'} (max_delta={default_max_weight_delta:.2f})")
        st.caption(
            f"value_tuning_bias: {'on' if default_value_tuning_bias_enabled else 'off'} "
            f"(min_items={default_value_tuning_min_items}, max_bias={default_value_tuning_max_bias:.2f})"
        )

        if st.button("⚙️ RLHF重み更新を実行", use_container_width=True):
            try:
                result = apply_reward_adjustments(
                    min_entries=default_min_entries,
                    min_csat=default_min_csat,
                    min_adoption_rate=default_min_adoption,
                    min_nps=default_min_nps,
                    ai_weight=default_ai_weight,
                    min_ai_entries=default_min_ai_entries,
                    min_ai_confidence=default_min_ai_confidence,
                    auto_aggregate_ai=default_auto_aggregate_ai,
                    enable_rlaif_delta_cap=default_enable_delta_cap,
                    rlaif_max_weight_delta=default_max_weight_delta,
                    enable_value_tuning_bias=default_value_tuning_bias_enabled,
                    value_tuning_min_items=default_value_tuning_min_items,
                    value_tuning_max_bias=default_value_tuning_max_bias,
                )
                status = result.get("status")
                if status == "ok":
                    source = result.get("source", "human_only")
                    source_label = "human+ai" if source == "human_ai_blended" else "human_only"
                    st.success(f"RLHF重み更新を適用しました。（source={source_label}）")
                    cap = result.get("weight_cap") or {}
                    if cap.get("enabled"):
                        if cap.get("was_clamped"):
                            st.warning("重み変動キャップが適用され、更新幅を制限しました。")
                            st.json(cap)
                        else:
                            st.caption("重み変動キャップ有効: 上限制限は発生しませんでした。")
                    blend_details = result.get("blend_details") or {}
                    if blend_details:
                        st.caption("RLAIFブレンド詳細")
                        st.json(blend_details)

                    value_tuning = result.get("value_tuning") or {}
                    if value_tuning.get("enabled"):
                        st.caption("Value Tuning重み補正")
                        st.json(value_tuning)

                    human_summary = result.get("human_summary") or {}
                    blended_summary = result.get("summary") or {}
                    if human_summary and blended_summary:
                        st.caption("human_only vs blended 指標比較")
                        x1, x2, x3 = st.columns(3)
                        with x1:
                            st.metric(
                                "CSAT",
                                f"{(blended_summary.get('csat_mean') or 0):.3f}",
                                delta=f"{((blended_summary.get('csat_mean') or 0) - (human_summary.get('csat_mean') or 0)):.3f}",
                            )
                        with x2:
                            st.metric(
                                "NPS",
                                f"{(blended_summary.get('nps_mean') or 0):.3f}",
                                delta=f"{((blended_summary.get('nps_mean') or 0) - (human_summary.get('nps_mean') or 0)):.3f}",
                            )
                        with x3:
                            st.metric(
                                "Adoption",
                                f"{(blended_summary.get('adoption_rate') or 0):.3f}",
                                delta=f"{((blended_summary.get('adoption_rate') or 0) - (human_summary.get('adoption_rate') or 0)):.3f}",
                            )
                    st.json(result)
                elif status == "skipped":
                    st.warning("ゲート条件未達のため更新をスキップしました。")
                    reasons = result.get("reasons") or []
                    if reasons:
                        st.write("判定理由:")
                        for reason in reasons:
                            st.write(f"- {reason}")
                    st.json(result.get("summary") or {})
                    blend_details = result.get("blend_details") or {}
                    if blend_details:
                        st.caption("RLAIFブレンド詳細")
                        st.json(blend_details)
                elif status == "missing_agg":
                    st.info("集計ファイルが見つかりません。先に集計を実行してください。")
                else:
                    st.info("RLHF更新結果")
                    st.json(result)
            except Exception as e:
                st.error(f"RLHF重み更新中にエラーが発生しました: {e}")

        show_logs = bool(st.session_state.get("rlhf_show_gate_logs", True))
        if show_logs:
            st.write("**最近のゲート判定ログ**")
            logs = _read_gate_logs(limit=30)
            if not logs:
                st.caption("ログはまだありません。")
            else:
                st.caption("Δ列は1つ前の実行結果との差分です。")
                rows = _build_gate_history_rows(logs)
                frame = _format_gate_history_rows(rows)
                st.dataframe(_style_gate_history_rows(frame), use_container_width=True)

        st.divider()
        st.subheader("🧪 ベンチマーク回帰ゲート")

        if not REGRESSION_GATE_AVAILABLE:
            st.info("回帰ゲートモジュールが利用できません。")
        else:
            result_files = _find_recent_benchmark_results(limit=2)
            if len(result_files) < 2:
                st.caption("比較可能なベンチマーク結果ファイルが2件以上ありません。")
                st.caption("results/benchmarks 配下に直近2回の結果があると自動表示されます。")
            else:
                baseline_file, current_file = result_files[1], result_files[0]
                st.caption(f"baseline: {os.path.basename(baseline_file)}")
                st.caption(f"current: {os.path.basename(current_file)}")

                try:
                    report = RegressionGate().compare(baseline_file, current_file)
                except Exception as exc:
                    st.error(f"回帰ゲートの評価に失敗しました: {exc}")
                    report = None

                if report is not None:
                    status_col1, status_col2, status_col3 = st.columns(3)
                    with status_col1:
                        st.metric("status", report.status)
                    with status_col2:
                        st.metric("regressed", report.summary.get("regressed_benchmarks", 0))
                    with status_col3:
                        st.metric("improved", report.summary.get("improved_benchmarks", 0))

                    if report.notes:
                        for note in report.notes:
                            st.caption(note)

                    if report.benchmark_deltas:
                        delta_rows = []
                        for item in report.benchmark_deltas:
                            delta_rows.append(
                                {
                                    "benchmark": item.benchmark_name,
                                    "regressions": ", ".join(item.regressions) or "-",
                                    "improvements": ", ".join(item.improvements) or "-",
                                }
                            )
                        st.dataframe(pd.DataFrame(delta_rows), use_container_width=True)

        st.divider()
        st.subheader("🧾 保存済み回帰ゲート履歴")

        saved_reports = _read_regression_gate_reports(limit=30)
        if not saved_reports:
            st.caption("保存済み回帰ゲートレポートはまだありません。")
            st.caption("--auto-gate 実行後に results/benchmarks 配下へ保存されます。")
        else:
            history_frame = _format_regression_gate_rows(saved_reports)
            st.dataframe(history_frame, use_container_width=True)

            status_counts = history_frame["status"].value_counts().reset_index()
            status_counts.columns = ["status", "count"]
            fig_status = px.bar(
                status_counts,
                x="status",
                y="count",
                title="Regression Gate Status Distribution",
                color="status",
                color_discrete_sequence=["#2ecc71", "#f39c12", "#e74c3c"],
            )
            fig_status.update_layout(height=280, showlegend=False)
            st.plotly_chart(fig_status, use_container_width=True)

        st.divider()
        st.subheader("📊 RAG評価履歴")

        rag_reports = _read_rag_evaluation_reports(limit=30)
        if not rag_reports:
            st.caption("保存済みRAG評価レポートはまだありません。")
            st.caption("RAG評価を保存すると factual_consistency と end_to_end_score の履歴が表示されます。")
        else:
            rag_frame = _format_rag_evaluation_rows(rag_reports)
            st.dataframe(rag_frame, use_container_width=True)

            trend_df = rag_frame.copy()
            if not trend_df.empty:
                trend_df["timestamp"] = pd.to_datetime(trend_df["timestamp"], errors="coerce")
                trend_df = trend_df.sort_values("timestamp")

                fig_rag = go.Figure()
                fig_rag.add_trace(go.Scatter(
                    x=trend_df["timestamp"],
                    y=trend_df["factual_consistency"],
                    mode="lines+markers",
                    name="factual_consistency",
                    line=dict(color="#e67e22", width=3),
                ))
                fig_rag.add_trace(go.Scatter(
                    x=trend_df["timestamp"],
                    y=trend_df["end_to_end"],
                    mode="lines+markers",
                    name="end_to_end_score",
                    line=dict(color="#3498db", width=3),
                ))
                fig_rag.update_layout(
                    title="RAG Evaluation Trend",
                    height=320,
                    yaxis_title="score",
                )
                st.plotly_chart(fig_rag, use_container_width=True)

        st.divider()
        st.subheader("🔍 評価差分ビュー（ケース単位）")

        if not EVALUATION_DIFF_AVAILABLE:
            st.caption("評価差分ビューアが利用できません。")
        elif len(rag_reports) < 2:
            st.caption("比較対象のRAG評価レポートが2件以上あると、ケース単位の差分を表示します。")
        else:
            baseline_record = rag_reports[1]
            current_record = rag_reports[0]
            baseline_path = baseline_record.get("_path")
            current_path = current_record.get("_path")

            if not baseline_path or not current_path:
                st.caption("比較対象レポートのパス情報が不足しています。")
            else:
                st.caption(f"baseline: {os.path.basename(baseline_path)}")
                st.caption(f"current: {os.path.basename(current_path)}")
                try:
                    diff_report = EvaluationDiffViewer().compare(baseline_path, current_path)
                except Exception as exc:
                    st.error(f"評価差分の比較に失敗しました: {exc}")
                    diff_report = None

                if diff_report is not None:
                    c1, c2, c3, c4, c5 = st.columns(5)
                    with c1:
                        st.metric("shared", getattr(diff_report, "shared_samples", 0))
                    with c2:
                        st.metric("improved", getattr(diff_report, "improved_samples", 0))
                    with c3:
                        st.metric("regressed", getattr(diff_report, "regressed_samples", 0))
                    with c4:
                        st.metric("added", getattr(diff_report, "added_samples", 0))
                    with c5:
                        st.metric("removed", getattr(diff_report, "removed_samples", 0))

                    diff_rows = _format_evaluation_diff_rows(diff_report)
                    if diff_rows.empty:
                        st.caption("共有ケースの改善/悪化は検出されませんでした。")
                    else:
                        st.dataframe(diff_rows.head(20), use_container_width=True)
                        # Allow user to select a case and show trace/evidence
                        try:
                            options = diff_rows["query"].fillna("").tolist()
                        except Exception:
                            options = [str(x) for x in diff_rows.index.tolist()]

                        if options:
                            sel = st.selectbox("表示するケースを選択してください", options)
                            if sel:
                                with st.expander("ケース詳細を表示"):
                                    baseline_path = baseline_record.get("_path")
                                    current_path = current_record.get("_path")
                                    try:
                                        viewer = TraceEvidenceViewer()
                                        baseline_case = None
                                        current_case = None
                                        if TRACE_EVIDENCE_AVAILABLE and baseline_path:
                                            try:
                                                baseline_case = viewer.build_case_trace(baseline_path, query=sel)
                                            except Exception:
                                                baseline_case = None
                                        if TRACE_EVIDENCE_AVAILABLE and current_path:
                                            try:
                                                current_case = viewer.build_case_trace(current_path, query=sel)
                                            except Exception:
                                                current_case = None

                                        col_a, col_b = st.columns(2)
                                        with col_a:
                                            st.markdown("**baseline**")
                                            if baseline_case is None:
                                                st.caption("baseline のケースが見つかりませんでした。")
                                            else:
                                                st.text(viewer.format_case(baseline_case))

                                        with col_b:
                                            st.markdown("**current**")
                                            if current_case is None:
                                                st.caption("current のケースが見つかりませんでした。")
                                            else:
                                                st.text(viewer.format_case(current_case))
                                    except Exception as exc:
                                        st.error(f"ケース詳細の表示に失敗しました: {exc}")
    
    def _render_memory_management(self):
        """Render Memory Management dashboard."""
        st.subheader("💾 Memory Management")
        
        st.write("""
        Advanced memory systems optimize retention and retrieval:
        - **Meta Memory**: Quality-based retention
        - **Procedural Memory**: Cached execution procedures
        - **Context-Aware Retrieval**: Smart memory search
        - **Adaptive Forgetting**: Intelligent pruning
        """)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                label="Memories Recorded",
                value=len(self.manager.execution_traces),
                help="Total execution memories"
            )
        
        with col2:
            st.metric(
                label="Procedural Cache",
                value=len(self.manager.procedural_memory.procedures),
                help="Cached procedures for reuse"
            )
        
        with col3:
            st.metric(
                label="Quality Tracked",
                value=len(self.manager.meta_memory.memory_quality_scores),
                help="Memories with quality scores"
            )
        
        # Memory health
        st.write("**Memory System Status:**")
        
        try:
            meta_stats = self.manager.meta_memory.get_statistics()
            meta_desc = f"Quality evaluation & retention (Avg Quality: **{meta_stats.get('average_quality', 0.0):.2f}**, Needs Consolidation: **{meta_stats.get('memories_needing_consolidation', 0)}**)"
        except Exception:
            meta_desc = "Quality evaluation and retention management"
            
        try:
            proc_stats = self.manager.procedural_memory.get_statistics()
            proc_desc = f"Cached execution procedures (Procedures: **{proc_stats.get('total_procedures', 0)}**, Parameter Patterns: **{proc_stats.get('parameter_patterns', 0)}**, Executions: **{proc_stats.get('total_executions', 0)}**)"
        except Exception:
            proc_desc = "Cached execution procedures"
            
        try:
            retrieval_stats = self.manager.context_retriever.get_retrieval_statistics()
            retrieval_desc = f"Semantic memory search (Retrievals: **{retrieval_stats.get('total_retrievals', 0)}**, Avg Confidence: **{retrieval_stats.get('avg_confidence', 0.0):.2f}**)"
        except Exception:
            retrieval_desc = "Semantic memory search"
            
        try:
            forget_stats = self.manager.adaptive_forgetting.get_statistics()
            forget_desc = f"Intelligent memory pruning (Avg Retention: **{forget_stats.get('avg_retention_score', 0.0):.2f}**, Forgotten: **{forget_stats.get('total_forgotten', 0)}**, Consolidated: **{forget_stats.get('total_consolidated', 0)}**)"
        except Exception:
            forget_desc = "Intelligent memory pruning"

        systems = [
            ("🧠 Meta Memory", meta_desc, "🟢"),
            ("⚙️ Procedural Memory", proc_desc, "🟢"),
            ("🔍 Context-Aware Retrieval", retrieval_desc, "🟢"),
            ("🗑️ Adaptive Forgetting", forget_desc, "🟢"),
        ]
        
        for name, desc, status in systems:
            st.write(f"{status} **{name}**")
            st.markdown(f"   {desc}")

    def _render_failure_cases(self):
        """Render Failure Cases dashboard."""
        if not FAILURE_CASE_AVAILABLE:
            st.warning("⚠️ Failure Case Collector is not available")
            return

        st.subheader("❌ Failure Case Analysis")

        # Initialize collector
        collector = FailureCaseCollector(storage_dir="results/failure_cases")

        # Show statistics
        stats = collector.get_statistics()

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                label="Total Cases",
                value=stats["total_cases"],
                help="Total failure cases collected"
            )

        with col2:
            critical = stats["severity_distribution"].get("critical", 0)
            st.metric(
                label="Critical",
                value=critical,
                help="High severity cases (severity >= 0.8)"
            )

        with col3:
            categories = len(stats["categories"])
            st.metric(
                label="Categories",
                value=categories,
                help="Number of failure categories"
            )

        with col4:
            tags = len(stats["top_tags"])
            st.metric(
                label="Tags",
                value=tags,
                help="Number of distinct tags"
            )

        # Display statistics
        if stats["categories"]:
            st.write("**Distribution by Category:**")
            category_data = [[k, v] for k, v in stats["categories"].items()]
            df_categories = pd.DataFrame(category_data, columns=["Category", "Count"])
            st.bar_chart(df_categories.set_index("Category"))

        # Display high priority cases
        if collector.cases:
            st.write("**Recent High Priority Cases:**")

            high_priority = collector.get_high_priority_cases(top_n=5)

            for i, case in enumerate(high_priority, 1):
                with st.expander(
                    f"#{i} - {case.category.upper()} (severity: {case.severity:.2f}) - {case.query[:50]}..."
                ):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.write("**Query:**")
                        st.write(case.query)
                        st.write("**Expected Answer:**")
                        st.write(case.expected_answer[:200] + "..." if len(case.expected_answer) > 200 else case.expected_answer)

                    with col2:
                        st.write("**Actual Answer:**")
                        st.write(case.actual_answer[:200] + "..." if len(case.actual_answer) > 200 else case.actual_answer)
                        st.write("**Severity:**")
                        st.write(f"{case.severity:.2f}")

                    if case.tags:
                        st.write("**Tags:**")
                        st.write(", ".join(case.tags))

                    if case.root_cause:
                        st.write("**Root Cause:**")
                        st.write(case.root_cause)

                    if case.notes:
                        st.write("**Notes:**")
                        st.write(case.notes)

        else:
            st.info("📊 No failure cases collected yet. Use the CLI tool to collect failures from benchmark results.")

    def _render_dataset_sanity(self):
        """Render Dataset Sanity checks."""
        if not DATASET_SANITY_AVAILABLE:
            st.warning("⚠️ Dataset Sanity Checker not available")
            return

        st.subheader("🧾 Dataset Sanity Checker")

        # Try to find a recent benchmark file as default
        recent_files = _find_recent_benchmark_results(limit=1)
        if recent_files:
            default_path = os.path.relpath(recent_files[0], os.getcwd())
        else:
            default_path = "results/benchmarks/latest.json"

        col1, col2 = st.columns(2)
        with col1:
            st.write("**Dataset file**")
            path_input = st.text_input("Dataset JSON path", value=default_path)
        with col2:
            run_button = st.button("Run checks")

        if run_button and path_input:
            p = Path(path_input)
            if not p.exists():
                st.error(f"File not found: {path_input}")
            else:
                report = collect_issues_from_file(str(p))
                if not report.get("success"):
                    st.error(f"Error: {report.get('error')}")
                else:
                    r = report.get("report", {})
                    st.metric("Total Samples", r.get("total", 0))
                    summary = r.get("summary", {})
                    
                    st.write("**Summary**")
                    col1, col2, col3, col4, col5 = st.columns(5)
                    with col1:
                        missing_keys = summary.get("missing_required_keys", 0)
                        status_icon = "✅" if missing_keys == 0 else "❌"
                        st.metric(label=f"{status_icon} 必須キー欠損", value=missing_keys)
                    with col2:
                        empty_vals = summary.get("empty_values", 0)
                        status_icon = "✅" if empty_vals == 0 else "⚠️"
                        st.metric(label=f"{status_icon} 空の値", value=empty_vals)
                    with col3:
                        mismatches = summary.get("type_mismatches", 0)
                        status_icon = "✅" if mismatches == 0 else "⚠️"
                        st.metric(label=f"{status_icon} 型ミスマッチ", value=mismatches)
                    with col4:
                        duplicates = summary.get("duplicates", 0)
                        status_icon = "✅" if duplicates == 0 else "⚠️"
                        st.metric(label=f"{status_icon} 重複クエリ", value=duplicates)
                    with col5:
                        ratio_issues = summary.get("length_ratio_issues", 0)
                        status_icon = "✅" if ratio_issues == 0 else "⚠️"
                        st.metric(label=f"{status_icon} 長さ比率異常", value=ratio_issues)

                    total_issues = sum(summary.values())
                    if total_issues == 0:
                        st.success("🎉 データセットの健全性に問題は検出されませんでした！")
                    else:
                        st.warning(f"⚠️ データセット内で合計 {total_issues} 件の潜在的な問題が検出されました。詳細は以下をご確認ください。")

                    if r.get("errors"):
                        st.subheader("Issues")
                        for e in r.get("errors")[:50]:
                            st.write(f"- {e}")

    def _render_evaluation_diffs(self):
        """Render evaluation diff viewer."""
        if not EVAL_DIFF_AVAILABLE:
            st.warning("⚠️ Evaluation Diff Viewer not available")
            return

        st.subheader("🔍 Evaluation Diff Viewer")
        
        recent_files = _find_recent_benchmark_results(limit=2)
        if len(recent_files) >= 2:
            default_b = os.path.relpath(recent_files[1], os.getcwd())
            default_c = os.path.relpath(recent_files[0], os.getcwd())
        else:
            default_b = "results/eval/baseline.json"
            default_c = "results/eval/current.json"

        col1, col2 = st.columns(2)
        with col1:
            baseline_path = st.text_input("Baseline JSON", value=default_b)
        with col2:
            current_path = st.text_input("Current JSON", value=default_c)

        run = st.button("Compare")
        if run:
            from pathlib import Path
            b = Path(baseline_path)
            c = Path(current_path)
            if not b.exists():
                st.error(f"Baseline not found: {baseline_path}")
                return
            if not c.exists():
                st.error(f"Current not found: {current_path}")
                return
            report = compute_diff_from_files(str(b), str(c))
            summary = report.get("summary", {})
            st.metric("Baseline samples", summary.get("total_baseline", 0))
            st.metric("Current samples", summary.get("total_current", 0))
            st.write("**Counts**")
            st.json({k: summary.get(k) for k in ["added", "removed", "improved", "regressed", "unchanged"]})

            top = report.get("top_regressions", [])
            if top:
                st.subheader("Top regressions")
                for r in top[:20]:
                    with st.expander(f"{r['id']} (Δ={r['delta']:.3f})"):
                        st.write("Baseline score:", r.get("baseline_score"))
                        st.write("Current score:", r.get("current_score"))
                        st.json({"baseline": r.get("baseline"), "current": r.get("current")})
            # Interactive table: filter / sort / search
            items = report.get("items", [])
            types = sorted({it.get("type") for it in items if it.get("type")})
            sel_type = st.selectbox("Filter type", options=["all"] + types, index=0)
            sort_by = st.selectbox("Sort by", options=["delta", "baseline_score", "current_score", "id"], index=0)
            desc = st.checkbox("Descending sort", value=True)
            q = st.text_input("Search id contains")

            def _match(it):
                if sel_type != "all" and it.get("type") != sel_type:
                    return False
                if q and q not in str(it.get("id", "")):
                    return False
                return True

            filtered = [it for it in items if _match(it)]
            try:
                filtered_sorted = sorted(filtered, key=lambda x: x.get(sort_by) if x.get(sort_by) is not None else 0, reverse=desc)
            except Exception:
                filtered_sorted = filtered

            if filtered_sorted:
                import pandas as _pd
                df_rows = []
                for it in filtered_sorted:
                    df_rows.append({
                        "id": it.get("id"),
                        "type": it.get("type"),
                        "baseline_score": it.get("baseline_score"),
                        "current_score": it.get("current_score"),
                        "delta": it.get("delta"),
                    })
                st.dataframe(_pd.DataFrame(df_rows), use_container_width=True)
                # CSV download
                try:
                    csv_bytes = report_to_csv_bytes({"items": filtered_sorted})
                    st.download_button(label="Download CSV", data=csv_bytes, file_name="eval_diff.csv", mime="text/csv")
                except Exception:
                    # best-effort: fallback to writing file
                    outp = "/tmp/eval_diff.csv"
                    import csv as _csv
                    with open(outp, "w", encoding="utf-8") as f:
                        w = _csv.writer(f)
                        w.writerow(["id", "type", "baseline_score", "current_score", "delta"])
                        for r in filtered_sorted:
                            w.writerow([r.get("id"), r.get("type"), r.get("baseline_score"), r.get("current_score"), r.get("delta")])
                    st.write(f"Wrote CSV to {outp}")

    def _render_model_architecture(self):
        """Render model architecture inspection and configuration tools."""
        st.subheader("🤖 モデルアーキテクチャ学習・観測ツール")
        st.write("""
        現在の自己学習システムで使用されるディープラーニングモデル（GPT vs Mamba）のパラメータを観測し、
        動的に切り替えて学習に反映させることができます。
        """)

        # 1. ロード処理
        config_dir = Path(os.getcwd()) / "config"
        config_path = config_dir / "model_config.json"
        
        # デフォルト値
        cfg = {
            "model_type": "gpt",
            "batch_size": 12,
            "block_size": 512,
            "n_layer": 6,
            "n_embd": 384,
            "n_head": 6,
            "d_state": 16,
            "d_conv": 4,
            "expand": 2
        }
        
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    cfg.update(loaded)
            except Exception:
                pass

        # 2. UIコントロールの構築
        col1, col2 = st.columns(2)
        with col1:
            st.write("#### 🧱 モデルパラメータ設定")
            model_type_selected = st.selectbox(
                "モデルタイプ (model_type)",
                options=["gpt", "mamba"],
                index=0 if cfg["model_type"] == "gpt" else 1,
                help="学習・推論に用いるニューラルネットワークのアーキテクチャを選択します。"
            )
            
            n_layer_val = st.slider(
                "レイヤー数 (n_layer)",
                min_value=1,
                max_value=32,
                value=int(cfg["n_layer"]),
                step=1,
                help="アテンションまたはSSMブロックを何段重ねるか決定します。"
            )
            
            n_embd_val = st.select_slider(
                "埋め込み次元数 (n_embd)",
                options=[64, 128, 256, 384, 512, 768, 1024],
                value=int(cfg["n_embd"]),
                help="トークンをベクトル化する次元数。大きいほど表現力が高まります。"
            )
            
            block_size_val = st.select_slider(
                "コンテキスト長 (block_size)",
                options=[32, 64, 128, 256, 512, 1024, 2048],
                value=int(cfg["block_size"]),
                help="モデルが一度に処理できる最大シーケンス長。Transformerでは計算量がこの二乗に比例します。"
            )

            batch_size_val = st.slider(
                "バッチサイズ (batch_size)",
                min_value=1,
                max_value=64,
                value=int(cfg["batch_size"]),
                step=1,
                help="一度にまとめて処理するデータのサンプル数。VRAM容量に応じて調整します。"
            )

        with col2:
            st.write("#### ⚙️ アーキテクチャ固有設定")
            if model_type_selected == "gpt":
                n_head_val = st.slider(
                    "マルチヘッド数 (n_head)",
                    min_value=1,
                    max_value=16,
                    value=int(cfg.get("n_head", 6)),
                    step=1,
                    help="アテンション機構のヘッド分割数（n_embdが割り切れる必要があります）。"
                )
                # Mambaパラメータは無効または保持
                d_state_val = int(cfg.get("d_state", 16))
                d_conv_val = int(cfg.get("d_conv", 4))
                expand_val = int(cfg.get("expand", 2))
                
                # パラメータ割り切れチェック
                if n_embd_val % n_head_val != 0:
                    st.error(f"❌ 警告: 埋め込み次元数 ({n_embd_val}) はマルチヘッド数 ({n_head_val}) で割り切れる必要があります！")
            else:
                d_state_val = st.slider(
                    "SSM状態次元 (d_state / N)",
                    min_value=4,
                    max_value=64,
                    value=int(cfg.get("d_state", 16)),
                    step=4,
                    help="状態空間モデル(SSM)における隠れ状態ベクトルの次元数。モデルの「記憶容量」に相当します。"
                )
                
                d_conv_val = st.slider(
                    "1D畳み込みカーネルサイズ (d_conv)",
                    min_value=2,
                    max_value=8,
                    value=int(cfg.get("d_conv", 4)),
                    step=1,
                    help="SSM入力前の局所トークン統合用1D畳み込みのカーネルサイズ。"
                )
                
                expand_val = st.slider(
                    "次元拡張率 (expand)",
                    min_value=1,
                    max_value=4,
                    value=int(cfg.get("expand", 2)),
                    step=1,
                    help="SSM内部の計算次元を何倍に広げるか決定します（expand * n_embd）。"
                )
                n_head_val = int(cfg.get("n_head", 6))

            # 3. パラメータ計算と比較表示
            st.write("#### 📊 アーキテクチャ理論比較")
            
            # パラメータ数簡易見積もり計算
            if model_type_selected == "gpt":
                layers_params = n_layer_val * (12 * (n_embd_val ** 2))
                total_est_params = (100000 * n_embd_val) + layers_params
                complexity_desc = f"コンテキスト長 L に対して **二次時間/メモリ空間 O(L²)** の計算負荷がかかります。推論時にはキー・バリューキャッシュ(KV Cache)が **O(L)** のサイズで増大し続けます。"
            else:
                d_inner = expand_val * n_embd_val
                layers_params = n_layer_val * ((d_inner * n_embd_val * 2) + (d_inner * (d_state_val * 2 + d_inner)) + (d_inner * n_embd_val))
                total_est_params = (100000 * n_embd_val) + layers_params
                complexity_desc = f"コンテキスト長 L に対して **線形時間/メモリ空間 O(L)** で処理可能です。推論時には前ステップの状態ベクトル H だけを持てばよいため、KVキャッシュが不要で **O(1)** の定数メモリで動作します。"
                
            st.info(f"**推定総パラメータ数 (語彙サイズ 100k):** {total_est_params / 1e6:.2f} M params")
            st.write(f"**計算量およびメモリ特性:**\n{complexity_desc}")

        # 4. 保存処理
        if st.button("💾 設定を保存して反映"):
            new_cfg = {
                "model_type": model_type_selected,
                "batch_size": batch_size_val,
                "block_size": block_size_val,
                "n_layer": n_layer_val,
                "n_embd": n_embd_val,
                "n_head": n_head_val,
                "d_state": d_state_val,
                "d_conv": d_conv_val,
                "expand": expand_val
            }
            try:
                config_dir.mkdir(exist_ok=True)
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(new_cfg, f, indent=4, ensure_ascii=False)
                st.success("✅ 設定を config/model_config.json に保存しました！次回の `train_gpt.py` や `generate.py` 実行時にこのパラメータが自動で読み込まれます。")
            except Exception as e:
                st.error(f"保存に失敗しました: {e}")

        # 5. フローダイアグラムの表示
        st.write("#### 🗺️ ブロックフロー図解 (ビジュアル表示)")
        
        gpt_code = """
graph TD
    Input["入力 x (B, T, n_embd)"] --> LN1["LayerNorm 1"]
    LN1 --> SelfAttn["Causal Self-Attention (Multi-Head)"]
    SelfAttn --> Add1["残差接続 (+)"]
    Input --> Add1
    
    Add1 --> LN2["LayerNorm 2"]
    LN2 --> MLP["MLP (Linear -> GELU -> Linear)"]
    MLP --> Add2["残差接続 (+)"]
    Add1 --> Add2
    
    Add2 --> Output["ブロック出力 (B, T, n_embd)"]
"""

        mamba_code = """
graph TD
    Input["入力 x (B, T, n_embd)"] --> Split{"分岐 (in_proj)"}
    
    %% SSM Branch
    Split -->|"SSMブランチ"| LinearSSM["Linear (SSM用射影)"]
    LinearSSM --> Conv1d["Conv1d (局所特徴の畳み込み)"]
    Conv1d --> SiLU1["SiLU (活性化)"]
    
    %% Selective SSM inputs
    SiLU1 --> ProjParams["パラメータ射影 (B, C, dt)"]
    ProjParams --> SelectiveSSM["Selective SSM (選択的状態スキャン)"]
    SiLU1 -->|"入力 u"| SelectiveSSM
    
    %% Gate Branch
    Split -->|"ゲートブランチ"| LinearGate["Linear (ゲート用射影)"]
    LinearGate --> SiLU2["SiLU (ゲートの活性化)"]
    
    %% Output Merge
    SelectiveSSM --> Mul["要素積 (*)"]
    SiLU2 --> Mul
    
    Mul --> OutProj["Linear (出力射影)"]
    OutProj --> Output["最終出力 (B, T, n_embd)"]
"""

        if st.__class__.__name__ == "_FakeStreamlit" or os.environ.get("PYTEST_CURRENT_TEST"):
            selected_code = gpt_code if model_type_selected == "gpt" else mamba_code
            st.code(selected_code.strip(), language="mermaid")
        else:
            if model_type_selected == "gpt":
                gpt_svg = """
<svg width="100%" height="520" viewBox="0 0 500 520" fill="none" xmlns="http://www.w3.org/2000/svg" style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; font-family: system-ui, -apple-system, sans-serif;">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#64748b"/>
    </marker>
  </defs>

  <rect width="100%" height="100%" rx="12" fill="#f8fafc"/>
  <text x="20" y="35" font-size="14" font-weight="bold" fill="#0f172a">GPT (Transformer Block) フロー図解</text>

  <!-- Input -->
  <rect x="150" y="60" width="200" height="34" rx="6" fill="#edf2f7" stroke="#cbd5e1" stroke-width="1.5"/>
  <text x="250" y="81" font-size="11" font-weight="600" fill="#1e293b" text-anchor="middle">入力 x (B, T, n_embd)</text>

  <!-- LN1 -->
  <rect x="170" y="120" width="160" height="28" rx="4" fill="#f1f5f9" stroke="#cbd5e1" stroke-width="1"/>
  <text x="250" y="137" font-size="11" fill="#475569" text-anchor="middle">LayerNorm 1</text>

  <!-- Self-Attn -->
  <rect x="160" y="170" width="180" height="34" rx="6" fill="#e1f5fe" stroke="#0288d1" stroke-width="1.5"/>
  <text x="250" y="191" font-size="11" font-weight="600" fill="#01579b" text-anchor="middle">Causal Self-Attention</text>

  <!-- Add 1 -->
  <rect x="220" y="230" width="60" height="26" rx="4" fill="#fff3e0" stroke="#f57c00" stroke-width="1.5"/>
  <text x="250" y="246" font-size="11" font-weight="bold" fill="#e65100" text-anchor="middle">＋ (Add)</text>

  <!-- LN2 -->
  <rect x="170" y="290" width="160" height="28" rx="4" fill="#f1f5f9" stroke="#cbd5e1" stroke-width="1"/>
  <text x="250" y="307" font-size="11" fill="#475569" text-anchor="middle">LayerNorm 2</text>

  <!-- MLP -->
  <rect x="160" y="340" width="180" height="34" rx="6" fill="#e1f5fe" stroke="#0288d1" stroke-width="1.5"/>
  <text x="250" y="361" font-size="11" font-weight="600" fill="#01579b" text-anchor="middle">MLP (Feed-Forward)</text>

  <!-- Add 2 -->
  <rect x="220" y="400" width="60" height="26" rx="4" fill="#fff3e0" stroke="#f57c00" stroke-width="1.5"/>
  <text x="250" y="416" font-size="11" font-weight="bold" fill="#e65100" text-anchor="middle">＋ (Add)</text>

  <!-- Output -->
  <rect x="150" y="456" width="200" height="34" rx="6" fill="#edf2f7" stroke="#cbd5e1" stroke-width="1.5"/>
  <text x="250" y="477" font-size="11" font-weight="600" fill="#1e293b" text-anchor="middle">ブロック出力 (B, T, n_embd)</text>

  <!-- Arrows -->
  <path d="M 250 94 L 250 120" stroke="#64748b" stroke-width="1.5" fill="none" marker-end="url(#arrow)"/>
  <path d="M 250 148 L 250 170" stroke="#64748b" stroke-width="1.5" fill="none" marker-end="url(#arrow)"/>
  <path d="M 250 204 L 250 230" stroke="#64748b" stroke-width="1.5" fill="none" marker-end="url(#arrow)"/>
  <path d="M 250 256 L 250 290" stroke="#64748b" stroke-width="1.5" fill="none" marker-end="url(#arrow)"/>
  <path d="M 250 318 L 250 340" stroke="#64748b" stroke-width="1.5" fill="none" marker-end="url(#arrow)"/>
  <path d="M 250 374 L 250 400" stroke="#64748b" stroke-width="1.5" fill="none" marker-end="url(#arrow)"/>
  <path d="M 250 426 L 250 456" stroke="#64748b" stroke-width="1.5" fill="none" marker-end="url(#arrow)"/>

  <!-- Residual 1 (Right side bypass) -->
  <path d="M 350 77 L 390 77 L 390 243 L 280 243" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="3,3" fill="none" marker-end="url(#arrow)"/>
  <text x="395" y="160" font-size="10" fill="#64748b" font-weight="bold">残差接続 1</text>

  <!-- Residual 2 (Left side bypass) -->
  <path d="M 250 270 L 110 270 L 110 413 L 220 413" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="3,3" fill="none" marker-end="url(#arrow)"/>
  <text x="60" y="340" font-size="10" fill="#64748b" font-weight="bold">残差接続 2</text>
</svg>
"""
                st.write(gpt_svg, unsafe_allow_html=True)
                with st.expander("📝 Mermaidテキストコードを表示"):
                    st.code(gpt_code.strip(), language="mermaid")
            else:
                mamba_svg = """
<svg width="100%" height="600" viewBox="0 0 600 600" fill="none" xmlns="http://www.w3.org/2000/svg" style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; font-family: system-ui, -apple-system, sans-serif;">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#64748b"/>
    </marker>
  </defs>

  <rect width="100%" height="100%" rx="12" fill="#f8fafc"/>
  <text x="20" y="35" font-size="14" font-weight="bold" fill="#0f172a">Mamba (Selective SSM Block) フロー図解</text>

  <!-- Input -->
  <rect x="200" y="60" width="200" height="34" rx="6" fill="#edf2f7" stroke="#cbd5e1" stroke-width="1.5"/>
  <text x="300" y="81" font-size="11" font-weight="600" fill="#1e293b" text-anchor="middle">入力 x (B, T, n_embd)</text>

  <!-- Split -->
  <rect x="200" y="120" width="200" height="30" rx="4" fill="#f1f5f9" stroke="#64748b" stroke-width="1.5"/>
  <text x="300" y="138" font-size="11" font-weight="bold" fill="#0f172a" text-anchor="middle">分岐 (in_proj)</text>

  <!-- LEFT: SSM Branch -->
  <rect x="60" y="180" width="160" height="28" rx="4" fill="#edf4ff" stroke="#7b9bd6" stroke-width="1"/>
  <text x="140" y="197" font-size="10" fill="#1f3a67" text-anchor="middle">Linear (SSM射影)</text>

  <rect x="60" y="230" width="160" height="28" rx="4" fill="#edf4ff" stroke="#7b9bd6" stroke-width="1"/>
  <text x="140" y="247" font-size="10" fill="#1f3a67" text-anchor="middle">Conv1d (1D畳み込み)</text>

  <rect x="60" y="280" width="160" height="28" rx="4" fill="#edf4ff" stroke="#7b9bd6" stroke-width="1"/>
  <text x="140" y="297" font-size="10" fill="#1f3a67" text-anchor="middle">SiLU (活性化)</text>

  <!-- Proj Params -->
  <rect x="140" y="330" width="120" height="28" rx="4" fill="#e8f5e9" stroke="#388e3c" stroke-width="1.2"/>
  <text x="200" y="347" font-size="9" font-weight="600" fill="#1b5e20" text-anchor="middle">パラメータ射影 (dt, B, C)</text>

  <!-- Selective SSM -->
  <rect x="60" y="380" width="160" height="34" rx="6" fill="#e1f5fe" stroke="#0288d1" stroke-width="1.5"/>
  <text x="140" y="401" font-size="11" font-weight="600" fill="#01579b" text-anchor="middle">Selective SSM</text>

  <!-- RIGHT: Gate Branch -->
  <rect x="380" y="180" width="160" height="28" rx="4" fill="#fcf8f2" stroke="#d69b7b" stroke-width="1"/>
  <text x="460" y="197" font-size="10" fill="#673a1f" text-anchor="middle">Linear (ゲート射影)</text>

  <rect x="380" y="280" width="160" height="28" rx="4" fill="#fcf8f2" stroke="#d69b7b" stroke-width="1"/>
  <text x="460" y="297" font-size="10" fill="#673a1f" text-anchor="middle">SiLU (ゲート活性化)</text>

  <!-- Multiply -->
  <rect x="220" y="440" width="160" height="30" rx="4" fill="#fff3e0" stroke="#f57c00" stroke-width="1.5"/>
  <text x="300" y="458" font-size="11" font-weight="bold" fill="#e65100" text-anchor="middle">要素積 (＊)</text>

  <!-- OutProj -->
  <rect x="200" y="495" width="200" height="30" rx="4" fill="#f1f5f9" stroke="#cbd5e1" stroke-width="1"/>
  <text x="300" y="513" font-size="10" fill="#475569" text-anchor="middle">Linear (出力射影)</text>

  <!-- Output -->
  <rect x="200" y="545" width="200" height="34" rx="6" fill="#edf2f7" stroke="#cbd5e1" stroke-width="1.5"/>
  <text x="300" y="566" font-size="11" font-weight="600" fill="#1e293b" text-anchor="middle">最終出力 (B, T, n_embd)</text>

  <!-- Arrows -->
  <path d="M 300 94 L 300 120" stroke="#64748b" stroke-width="1.5" fill="none" marker-end="url(#arrow)"/>
  
  <!-- Split to Left -->
  <path d="M 200 135 L 140 135 L 140 180" stroke="#64748b" stroke-width="1.5" fill="none" marker-end="url(#arrow)"/>
  <!-- Split to Right -->
  <path d="M 400 135 L 460 135 L 460 180" stroke="#64748b" stroke-width="1.5" fill="none" marker-end="url(#arrow)"/>

  <!-- Left flow -->
  <path d="M 140 208 L 140 230" stroke="#64748b" stroke-width="1.5" fill="none" marker-end="url(#arrow)"/>
  <path d="M 140 258 L 140 280" stroke="#64748b" stroke-width="1.5" fill="none" marker-end="url(#arrow)"/>
  
  <!-- SiLU1 to ProjParams -->
  <path d="M 140 308 L 140 320 L 200 320 L 200 330" stroke="#64748b" stroke-width="1.2" fill="none" marker-end="url(#arrow)"/>
  <!-- SiLU1 to SSM (input u) -->
  <path d="M 110 308 L 110 380" stroke="#64748b" stroke-width="1.5" fill="none" marker-end="url(#arrow)"/>
  <text x="75" y="347" font-size="9" fill="#64748b">入力 u</text>

  <!-- ProjParams to SSM -->
  <path d="M 200 358 L 200 370 L 170 370 L 170 380" stroke="#64748b" stroke-width="1.2" fill="none" marker-end="url(#arrow)"/>

  <!-- Right flow -->
  <path d="M 460 208 L 460 280" stroke="#64748b" stroke-width="1.5" fill="none" marker-end="url(#arrow)"/>

  <!-- Merge to Multiply -->
  <!-- Left SSM to Multiply -->
  <path d="M 140 414 L 140 455 L 220 455" stroke="#64748b" stroke-width="1.5" fill="none" marker-end="url(#arrow)"/>
  <!-- Right SiLU2 to Multiply -->
  <path d="M 460 308 L 460 455 L 380 455" stroke="#64748b" stroke-width="1.5" fill="none" marker-end="url(#arrow)"/>

  <!-- Multiply to OutProj -->
  <path d="M 300 470 L 300 495" stroke="#64748b" stroke-width="1.5" fill="none" marker-end="url(#arrow)"/>
  <!-- OutProj to Output -->
  <path d="M 300 525 L 300 545" stroke="#64748b" stroke-width="1.5" fill="none" marker-end="url(#arrow)"/>
</svg>
"""
                st.write(mamba_svg, unsafe_allow_html=True)
                with st.expander("📝 Mermaidテキストコードを表示"):
                    st.code(mamba_code.strip(), language="mermaid")


def render_learning_dashboard():
    """Main function to render the learning dashboard in Streamlit."""
    if not PHASE5_AVAILABLE:
        st.warning("Phase 5 Learning Systems are not installed")
        return
    
    dashboard = LearningDashboard()
    dashboard.render()


def add_learning_panel_to_sidebar():
    """Add a learning panel to the Streamlit sidebar."""
    st.sidebar.markdown("---")
    st.sidebar.subheader("🧠 Learning Systems")
    
    if not PHASE5_AVAILABLE:
        st.sidebar.warning("Phase 5 not available")
        return
    
    manager = get_phase5_manager()
    stats = manager.get_learning_statistics()
    
    st.sidebar.metric(
        "Executions",
        stats["total_executions"],
        help="Total task executions"
    )
    st.sidebar.metric(
        "Success Rate",
        f"{stats['success_rate']:.0%}",
        help="Percentage successful"
    )
    
    if st.sidebar.button("📊 View Learning Dashboard"):
        # Set the app page to the Learning Dashboard and request a rerun
        st.session_state.show_dashboard = True
        try:
            st.session_state.app_page = "🧠 Learning Dashboard"
        except Exception:
            pass
        try:
            st.experimental_rerun()
        except Exception:
            # If rerun isn't available in this context, proceed without crashing
            pass
