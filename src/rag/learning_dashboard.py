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
                rows = []
                for item in logs:
                    summary = item.get("summary") or {}
                    rows.append({
                        "timestamp": item.get("timestamp", ""),
                        "status": item.get("status", ""),
                        "source": item.get("source", "human_only"),
                        "reasons": ", ".join(item.get("reasons") or []),
                        "entries": summary.get("total_entries"),
                        "csat": summary.get("csat_mean"),
                        "nps": summary.get("nps_mean"),
                        "adoption": summary.get("adoption_rate"),
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True)
    
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
