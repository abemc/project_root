"""Dynamic Task Manager (minimal skeleton)

Provides a lightweight runtime that can accept an ExecutionPlan and drive execution
via a provided executor. This is intentionally minimal: priority evaluation and
replanning hooks are pluggable and currently use simple defaults.
"""
from typing import Dict, Optional
import logging

from .agent_engine import ExecutionPlan, ToolResult

logger = logging.getLogger(__name__)


class DynamicTaskManager:
    """DynamicTaskManager (improved priority logic)

    Priority evaluation considers multiple signals. The `evaluate_priorities`
    method accepts an optional `task_context` mapping where callers can provide
    historical metrics per task (e.g. success rate, estimated_time, urgency).
    """
    # default weight configuration
    DEFAULT_WEIGHTS = {
        "success": 0.5,
        "urgency": 0.25,
        "efficiency": 0.2,
        "dependency_penalty": 0.1,
    }

    def __init__(self, planner=None, executor=None, monitor=None, weights: dict = None):
        self.planner = planner
        self.executor = executor
        self.monitor = monitor
        self.weights = {**self.DEFAULT_WEIGHTS, **(weights or {})}
        # circuit breaker state per tool: {tool_name: {"fail_count": int, "tripped_until": float}}
        self.tool_circuit: Dict[str, dict] = {}
        self.circuit_threshold = 3
        self.circuit_cooldown = 30  # seconds
        # attempt to load a RAG store if available
        try:
            from src.rag.embed_store import FaissStore
            import os
            idx_path = os.path.join('corpus', 'rag_store.index')
            meta_path = os.path.join('corpus', 'rag_store_meta.json')
            if os.path.exists(idx_path):
                self.rag_store = FaissStore(index_path=idx_path, meta_path=meta_path)
            else:
                self.rag_store = None
        except Exception:
            self.rag_store = None

    def evaluate_priorities(self, plan: ExecutionPlan, task_context: Optional[Dict[str, dict]] = None) -> Dict[str, float]:
        """Compute priority score per task.

        task_context: optional mapping: task_id -> {
            'historical_success_rate': float (0-1),
            'estimated_time': float (seconds),
            'urgency': float (0-1)
        }

        If a value is missing, sensible defaults are used.
        """
        task_context = task_context or {}
        scores: Dict[str, float] = {}

        # helper normalizers
        def norm_time(t):
            try:
                t = float(t)
                return 1.0 / (1.0 + max(0.0, t))
            except Exception:
                return 0.5

        for st in plan.subtasks:
            tid = st.task_id
            ctx = task_context.get(tid, {})

            success = float(ctx.get("historical_success_rate", 0.7))
            urgency = float(ctx.get("urgency", 0.5))
            est_time = ctx.get("estimated_time", getattr(st, "estimated_time", None))
            est_eff = norm_time(est_time)

            # dependency penalty: number of dependencies (if present on subtask)
            deps = getattr(st, "dependencies", None) or []
            dep_penalty = len(deps) * self.weights.get("dependency_penalty", 0.1)

            w_s = self.weights.get("success", 0.5)
            w_u = self.weights.get("urgency", 0.25)
            w_e = self.weights.get("efficiency", 0.2)

            raw_score = (w_s * success) + (w_u * urgency) + (w_e * est_eff)
            score = max(0.0, raw_score - dep_penalty)
            scores[tid] = round(score, 4)

        # normalize to 0-1 by dividing by max observed
        maxv = max(scores.values()) if scores else 1.0
        if maxv > 0:
            for k in scores:
                scores[k] = round(scores[k] / maxv, 4)

        return scores

    def replan_if_needed(self, plan: ExecutionPlan, task_context: Optional[Dict[str, dict]] = None) -> ExecutionPlan:
        """Recompute execution_order based on current priorities while respecting dependencies.

        Returns a new plan with updated `execution_order`.
        """
        task_context = task_context or {}
        scores = self.evaluate_priorities(plan, task_context=task_context)

        # Simple dependency-aware ordering: pick highest-score task whose dependencies are satisfied
        remaining = {st.task_id: st for st in plan.subtasks}
        ordered = []

        def deps_satisfied(tid):
            deps = getattr(remaining[tid], "dependencies", None) or []
            return all(d in ordered for d in deps)

        # iterate until all placed
        while remaining:
            # candidates whose deps satisfied
            candidates = [tid for tid in remaining.keys() if deps_satisfied(tid)]
            if not candidates:
                # cyclic or unmet deps; append remaining in arbitrary order
                ordered.extend(list(remaining.keys()))
                break
            # choose candidate with max score
            best = max(candidates, key=lambda t: scores.get(t, 0.0))
            ordered.append(best)
            del remaining[best]

        plan.execution_order = ordered
        return plan

    def execute_plan(self, plan: ExecutionPlan, user_approvals: Optional[Dict[str,bool]] = None,
                     task_context: Optional[Dict[str, dict]] = None,
                     update_context_callback: Optional[callable] = None) -> Dict:
        """Execute subtasks sequentially using the provided executor.

        Returns a summary dict with results and simple metrics.
        """
        summary = {
            "goal": plan.main_goal,
            "execution_plan": {"execution_order": plan.execution_order},
            "results": {},
            "failed_tasks": [],
        }

        # initial replan based on provided context
        plan = self.replan_if_needed(plan, task_context=task_context)

        for task_id in list(plan.execution_order):
            subtask = next((s for s in plan.subtasks if s.task_id == task_id), None)
            if not subtask:
                logger.warning(f"Subtask {task_id} not found in plan.subtasks")
                summary["failed_tasks"].append(task_id)
                continue

            tool_name = subtask.required_tools[0] if subtask.required_tools else None
            if not tool_name or not self.executor:
                summary["results"][task_id] = {"status": "skipped", "result": None}
                continue

            # check circuit breaker for this tool
            circ = self.tool_circuit.get(tool_name, {})
            import time
            now = time.time()
            if circ.get("tripped_until", 0) > now:
                summary["results"][task_id] = {"status": "skipped", "result": None, "reason": "circuit_tripped"}
                continue

            # attempt execution; executor.execute_tool expected to return ToolResult-like
            try:
                # if rag_store available, fetch relevant docs for this subtask
                params = {}
                try:
                    if getattr(self, 'rag_store', None) is not None:
                        qv = self.rag_store.embed_fn(subtask.description or '')
                        docs = self.rag_store.search(qv, top_k=5)
                        params = {"query": subtask.description, "docs": docs}
                except Exception:
                    params = {}

                res = self.executor.execute_tool(tool_name, params)
                if hasattr(res, "status"):
                    status = getattr(res, "status")
                    result = getattr(res, "result", None)
                elif isinstance(res, dict):
                    status = res.get("status", "success")
                    result = res.get("result")
                else:
                    status = "success"
                    result = res

                summary["results"][task_id] = {"status": status, "result": result}
                if status != "success":
                    summary["failed_tasks"].append(task_id)
                    # increment circuit breaker failure count
                    circ = self.tool_circuit.get(tool_name, {"fail_count": 0, "tripped_until": 0})
                    circ["fail_count"] = circ.get("fail_count", 0) + 1
                    if circ["fail_count"] >= self.circuit_threshold:
                        circ["tripped_until"] = now + self.circuit_cooldown
                    self.tool_circuit[tool_name] = circ
                else:
                    # on success, reset failure count
                    if tool_name in self.tool_circuit:
                        self.tool_circuit[tool_name]["fail_count"] = 0

            except Exception as exc:
                logger.exception("Tool execution failed")
                summary["results"][task_id] = {"status": "error", "result": str(exc)}
                summary["failed_tasks"].append(task_id)
                # count as failure for circuit breaker
                circ = self.tool_circuit.get(tool_name, {"fail_count": 0, "tripped_until": 0})
                circ["fail_count"] = circ.get("fail_count", 0) + 1
                if circ["fail_count"] >= self.circuit_threshold:
                    circ["tripped_until"] = now + self.circuit_cooldown
                self.tool_circuit[tool_name] = circ

            # after each task, allow external update to task_context and possibly replan remaining tasks
            # Monitor-driven sampling + external update callback can trigger replanning
            # Determine resource usage from tool result if present
            resource_usage = {}
            try:
                # res may be a ToolResult dataclass-like or a dict
                if isinstance(res, dict):
                    resource_usage = res.get("resource_usage") or res.get("resource_impact") or {}
                else:
                    r = getattr(res, "result", None)
                    if isinstance(r, dict):
                        resource_usage = r.get("resource_usage") or r.get("resource_impact") or {}
            except Exception:
                resource_usage = {}

            # if monitor exists, check constraints and trigger replanning when violated
            if self.monitor:
                try:
                    # if no explicit usage provided, attempt lightweight sampling via psutil
                    if not resource_usage:
                        try:
                            import psutil
                            resource_usage = {
                                "cpu_percent": psutil.cpu_percent(interval=0.05),
                                "memory_percent": psutil.virtual_memory().percent,
                            }
                        except Exception:
                            resource_usage = {}

                    if resource_usage:
                        ok, violations = self.monitor.check_constraints(resource_usage)
                        if not ok:
                            # record an alert with useful context
                            self.monitor.add_alert(
                                severity="warning",
                                message=f"Resource constraint violation during task {task_id}: {violations}",
                                recommended_action="Replan remaining tasks or scale resources"
                            )
                            # update task_context to deprioritize long tasks (simple heuristic)
                            task_context = task_context or {}
                            for st in plan.subtasks:
                                if st.task_id not in summary["results"]:
                                    # reduce urgency for long estimated tasks
                                    existing = task_context.get(st.task_id, {})
                                    est = existing.get("estimated_time", getattr(st, "estimated_time", None) or 0)
                                    if est and est > 10:
                                        existing = {**existing, "urgency": max(0.0, float(existing.get("urgency", 0.5)) - 0.4)}
                                    task_context[st.task_id] = existing
                            # replan remaining tasks immediately
                            remaining_tasks = [t for t in plan.execution_order if t not in list(summary["results"].keys())]
                            if remaining_tasks:
                                subplan = ExecutionPlan(main_goal=plan.main_goal, subtasks=[s for s in plan.subtasks if s.task_id in remaining_tasks], execution_order=remaining_tasks)
                                subplan = self.replan_if_needed(subplan, task_context=task_context)
                                plan.execution_order = [t for t in plan.execution_order if t in list(summary["results"].keys())] + subplan.execution_order
                except Exception:
                    logger.exception("Monitor check failed")

            if update_context_callback:
                try:
                    new_ctx = update_context_callback(task_id, summary)
                    if isinstance(new_ctx, dict):
                        task_context = {**(task_context or {}), **new_ctx}
                        # replan remaining tasks
                        remaining_tasks = [t for t in plan.execution_order if t not in list(summary["results"].keys())]
                        if remaining_tasks:
                            # build a subplan view for replanning
                            subplan = ExecutionPlan(main_goal=plan.main_goal, subtasks=[s for s in plan.subtasks if s.task_id in remaining_tasks], execution_order=remaining_tasks)
                            subplan = self.replan_if_needed(subplan, task_context=task_context)
                            # replace remaining order in original plan
                            plan.execution_order = [t for t in plan.execution_order if t in list(summary["results"].keys())] + subplan.execution_order
                except Exception:
                    pass

        return summary
