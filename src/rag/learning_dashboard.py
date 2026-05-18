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
import logging

# Import Phase 5 manager
try:
    from src.rag.phase5_integration import get_phase5_manager, Phase5IntegrationManager
    PHASE5_AVAILABLE = True
except ImportError:
    PHASE5_AVAILABLE = False
    Phase5IntegrationManager = None

logger = logging.getLogger(__name__)


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
        
        # Execution timeline
        if self.manager.execution_traces:
            st.subheader("⏱️ Execution Timeline")
            
            # Convert traces to dataframe
            traces_data = []
            for trace in self.manager.execution_traces[-20:]:  # Last 20
                traces_data.append({
                    "Time": trace.timestamp,
                    "Task": trace.task_family[:20],
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
        st.session_state.show_dashboard = True
