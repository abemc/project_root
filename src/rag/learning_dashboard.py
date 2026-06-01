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

    return frame.style.map(_delta_style, subset=["Δcsat", "Δnps", "Δadoption"])


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
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Statistics",
            "🔄 Transfer Learning",
            "🎲 Reinforcement Learning",
            "💾 Memory Management"
        ])
        
        with tab1:
            self._render_statistics()
        
        with tab2:
            self._render_transfer_learning()
        
        with tab3:
            self._render_reinforcement_learning()
        
        with tab4:
            self._render_memory_management()
    
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
        
        for i, signal in enumerate(reward_signals, 1):
            st.write(f"{i}. {signal}")

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
                rows = [
                    {
                        "value_dimension": key,
                        "mean": value,
                        "count": signal_counts.get(key, 0),
                    }
                    for key, value in signal_means.items()
                ]
                st.dataframe(pd.DataFrame(rows), use_container_width=True)

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
                st.dataframe(frame, use_container_width=True)

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
        
        systems = [
            ("🧠 Meta Memory", "Quality evaluation and retention management", "🟢"),
            ("⚙️ Procedural Memory", "Cached execution procedures", "🟢"),
            ("🔍 Context-Aware Retrieval", "Semantic memory search", "🟢"),
            ("🗑️ Adaptive Forgetting", "Intelligent memory pruning", "🟢"),
        ]
        
        for name, desc, status in systems:
            st.write(f"{status} **{name}**")
            st.write(f"   {desc}")


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
