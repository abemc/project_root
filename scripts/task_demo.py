#!/usr/bin/env python3
"""Simple demo to exercise AgentEngine.execute_goal()

This script attempts to import the project's AgentEngine and call execute_goal().
If the import fails (missing deps), a fallback mock will run to demonstrate the flow.
"""
import argparse
import json


def run_with_agent_engine(goal, auto_approve=False):
    try:
        from src.agent_architecture.agent_engine import AgentEngine, AutonomyLevel, Tool, ToolType

        engine = AgentEngine(AutonomyLevel.SEMI_AUTONOMOUS)

        # Register minimal mock tools so planner-generated tasks can execute
        def mock_web_search(query: str = ""):
            return ["doc1: 見積り", "doc2: 設計", "doc3: 使い方"]

        def mock_summarizer(docs=None):
            docs = docs or []
            texts = []
            for d in docs:
                if isinstance(d, dict):
                    texts.append(d.get('text') or d.get('result') or str(d))
                else:
                    texts.append(str(d))
            parts = []
            for t in texts:
                if ':' in t:
                    parts.append(t.split(':', 1)[0])
                elif '：' in t:
                    parts.append(t.split('：', 1)[0])
                else:
                    parts.append(t)
            return "；".join(parts) + " の要約（ダミー）"

        # Wrap into Tool dataclasses and register
        try:
            engine.executor.register_tool(Tool(name="web_search", tool_type=ToolType.INFORMATION, description="Mock web search", execute_fn=mock_web_search))
            engine.executor.register_tool(Tool(name="summarizer", tool_type=ToolType.REASONING, description="Mock summarizer", execute_fn=mock_summarizer))
        except Exception:
            # best-effort registration; continue even if fails
            pass

        user_approvals = {} if auto_approve else None
        res = engine.execute_goal(goal, {"available_tools": list(engine.executor.tools.keys())}, user_approvals=user_approvals, use_dynamic_manager=False)

        # Convert any ToolResult-like objects to serializable dicts
        def sanitize(obj):
            try:
                # ToolResult has attributes we can extract
                attrs = ["tool_name", "status", "result", "error_message", "execution_time", "confidence"]
                if hasattr(obj, "__dict__"):
                    od = {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
                    return od
            except Exception:
                pass
            return obj

        # Walk results if present
        if isinstance(res, dict) and "results" in res:
            sanitized = {}
            for k, v in res["results"].items():
                sanitized[k] = sanitize(v)
            res["results"] = sanitized

        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"AgentEngine import/exec failed: {exc}\nFalling back to mock demo.")
        return run_fallback_demo(goal)


def run_fallback_demo(goal):
    # Lightweight mock to illustrate plan->execute->result
    plan = {
        "main_goal": goal,
        "execution_order": ["task_1", "task_2"],
        "subtasks": [
            {"task_id": "task_1", "description": "search docs", "required_tools": ["search_doc"]},
            {"task_id": "task_2", "description": "summarize", "required_tools": ["summarizer"]},
        ],
        "estimated_steps": 2,
        "status": "ready",
    }

    results = {}
    for st in plan["subtasks"]:
        tid = st["task_id"]
        if "search" in st["description"]:
            results[tid] = {"status": "success", "result": ["doc1", "doc2", "doc3"]}
        else:
            results[tid] = {"status": "success", "result": "短い要約（ダミー）"}

    out = {"goal": goal, "execution_plan": plan, "results": results}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("goal", help="Goal to execute")
    p.add_argument("--auto-approve", action="store_true", help="Auto approve tasks that require approval")
    p.add_argument("--use-dtm", action="store_true", help="Use DynamicTaskManager if available")
    args = p.parse_args()
    if args.use_dtm:
        # Attempt to use AgentEngine -> planner -> DynamicTaskManager
        try:
            from src.agent_architecture.agent_engine import AgentEngine, AutonomyLevel
            from src.agent_architecture.dynamic_task_manager import DynamicTaskManager

            engine = AgentEngine(AutonomyLevel.SEMI_AUTONOMOUS)
            # register same mock tools for DTM execution path
            def mock_web_search(query: str = ""):
                return ["doc1: 見積り", "doc2: 設計", "doc3: 使い方"]

            def mock_summarizer(docs=None):
                docs = docs or []
                texts = []
                for d in docs:
                    if isinstance(d, dict):
                        texts.append(d.get('text') or d.get('result') or str(d))
                    else:
                        texts.append(str(d))
                parts = []
                for t in texts:
                    if ':' in t:
                        parts.append(t.split(':', 1)[0])
                    elif '：' in t:
                        parts.append(t.split('：', 1)[0])
                    else:
                        parts.append(t)
                return "；".join(parts) + " の要約（ダミー）"

            try:
                from src.agent_architecture.agent_engine import Tool, ToolType
                engine.executor.register_tool(Tool(name="web_search", tool_type=ToolType.INFORMATION, description="Mock web search", execute_fn=mock_web_search))
                engine.executor.register_tool(Tool(name="summarizer", tool_type=ToolType.REASONING, description="Mock summarizer", execute_fn=mock_summarizer))
            except Exception:
                pass
            planner = engine.planner
            plan = planner.decompose_task(args.goal, {"available_tools": []})
            dtm = DynamicTaskManager(planner=planner, executor=engine.executor, monitor=None)
            summary = dtm.execute_plan(plan, user_approvals={} if args.auto_approve else None)
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return_code = 0
        except Exception as exc:
            print(f"DTM run failed: {exc}\nFalling back to regular demo.")
            return_code = run_with_agent_engine(args.goal, auto_approve=args.auto_approve)
    else:
        return_code = run_with_agent_engine(args.goal, auto_approve=args.auto_approve)
    raise SystemExit(return_code)


if __name__ == "__main__":
    main()
