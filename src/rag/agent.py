# src/rag/agent.py

from .llm import call_llm
from .prompts import PLAN_PROMPT, GRADE_PROMPT, REWRITE_PROMPT, ANSWER_PROMPT, EVALUATE_ANSWER_PROMPT
from .retriever import Retriever
from .reranker import Reranker
from .logger import save_history
from .memory import MemoryManager
from .query_preprocessor import Phase7QueryPreprocessor
from .knowledge_integration_engine import Phase7KnowledgeIntegrationEngine
from .multi_domain_retriever import MultiDomainRetriever
from collections import OrderedDict, Counter
from src.rag.sandbox import Sandbox
from src.phase19.security_manager import SecurityManager
from src.performance.cache_optimizer import get_cache_optimizer
from src.performance.query_optimizer import QueryOptimizer
from src.performance.index_strategy import IndexStrategy
from src.reliability.circuit_breaker import CircuitBreaker
from src.reliability.retry_manager import RetryManager
from src.reliability.sla_monitor import SLAMonitor
from src.reliability.failover_strategy import FailoverStrategy
from .web_search import search_web_tool
from src.rag.date_utils import parse_relative_date
import json
import datetime
import time
import logging
import os
import subprocess
from pathlib import Path

try:
    from src.ethics.ethics_monitor import EthicsMonitor
    ethics_available = True
except ImportError:
    EthicsMonitor = None
    ethics_available = False

logger = logging.getLogger(__name__)

TOOLS = {
    "search_doc": "ローカルのコーパスを検索する。",
    "search_web": "Webを検索する。",
    "evaluate_docs": "文書の十分性を評価する。",
    "rewrite_query": "クエリを書き換える。",
    "read_file": "ファイルを読み込む。",
    "write_file": "ファイルを書き込む。",
    "run_shell": "シェルコマンドを実行する。",
    "python_interpreter": "Pythonコードを実行する。",
    "answer": "最終回答を生成する。",
}

class RAGAgent:
    def __init__(
        self,
        question,
        retriever,
        reranker,
        max_steps=10,
        llm_model="qwen2.5:7b",
        retrieval_top_k=10,
        rerank_top_k=5,
        system_prompt=None,
        history=None,
        strict_ethics=False,
        save_response_log=False,
    ):
        self.question = question
        self.retriever = retriever
        self.reranker = reranker
        self.max_steps = max_steps
        self.llm_model = llm_model
        self.retrieval_top_k = retrieval_top_k
        self.rerank_top_k = rerank_top_k
        self.system_prompt = system_prompt
        self.history = history if history else []
        self.used_queries = set()
        self.strict_ethics = strict_ethics
        self.save_response_log = save_response_log
        self.ethics_monitor = EthicsMonitor() if ethics_available else None
        self.ethics_log_path = Path("logs") / "ethics_audit.jsonl"
        self.response_log_path = Path("logs") / "agent_responses.jsonl"
        self.log_max_bytes = self._safe_int(os.getenv("RAG_LOG_MAX_BYTES", "5242880"), 5 * 1024 * 1024)
        self.log_backup_count = self._safe_int(os.getenv("RAG_LOG_BACKUP_COUNT", "3"), 3)
        
        self.autonomous_mode = bool(os.getenv("RAG_AUTO_MODE", "false").lower() == "true")
        self.action_history = []
        self.memory_manager = MemoryManager(retriever)
        self.sandbox = Sandbox()
        
        # Phase 19: Security Manager 統合
        self.security_manager = SecurityManager()
        self.security_manager.initialize_encryption()
        
        # Phase 19: Cache Optimizer 統合
        self.cache_optimizer = get_cache_optimizer()
        
        # Phase 19: Performance Optimizers
        self.query_optimizer = QueryOptimizer(self.retriever)
        self.index_strategy = IndexStrategy(self.retriever)
        
        # Phase 19: Reliability Manager
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        self.retry_manager = RetryManager(max_retries=3, base_delay=1.0)
        self.sla_monitor = SLAMonitor()
        
        # Phase 7: マルチドメイン処理
        self.query_preprocessor = Phase7QueryPreprocessor()
        self.knowledge_integrator = Phase7KnowledgeIntegrationEngine()
        self.domain_context = {}
        
        self.state = {
            "question": question,
            "original_question": question,
            "steps": 0,
            "history": [],
            "retrievals": [],
            "current_docs": [],
            "memories": [],
            "plan": "",
            "confidence": 0.0,
            "final_answer": "",
        }

        self.log_data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "question": question,
            "trace": [],
            "final_answer": None,
        }

        self._recall_memories()
        self.step_count = 0
        self.consecutive_fail_count = 0
        self.finished = False
        self.waiting_for_user = False
        self.current_answer_draft = None
        self.rejected_drafts = []

        # 自己改善エンジン統合
        from src.agent_architecture.agent_engine import SelfImprovement
        self._self_improvement = SelfImprovement()

        from .utils import format_tools_for_prompt
        self.tools_description, self.tool_names = format_tools_for_prompt(TOOLS)

    def _estimate_confidence_from_docs(self) -> float:
        docs = self.state.get("current_docs", [])
        if not docs: return 0.10
        scores = []
        for doc in docs[:5]:
            raw = doc.get("rerank_score", doc.get("score", 0.0))
            try: scores.append(float(raw))
            except: scores.append(0.0)
        top_score = max(scores) if scores else 0.0
        return round((min(len(docs), 5) / 5.0 * 0.5) + (max(0.0, min(top_score, 1.0)) * 0.5), 2)

    @staticmethod
    def _safe_int(value, default: int) -> int:
        try: return int(value)
        except: return default

    def _rotate_jsonl_if_needed(self, path: Path) -> None:
        if self.log_max_bytes <= 0 or not path.exists(): return
        if path.stat().st_size < self.log_max_bytes: return
        for i in range(self.log_backup_count - 1, 0, -1):
            src, dst = path.with_name(f"{path.name}.{i}"), path.with_name(f"{path.name}.{i+1}")
            if src.exists(): src.rename(dst)
        path.rename(path.with_name(f"{path.name}.1"))

    def _persist_jsonl(self, path: Path, payload: dict) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._rotate_jsonl_if_needed(path)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception as e: logger.warning(f"Log save error: {e}")

    def _audit_answer(self, answer: str) -> dict:
        if not self.ethics_monitor: return {"enabled": False}
        res_id = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        audit = self.ethics_monitor.audit_response(res_id, answer, {"question": self.question})
        res = {"status": audit.status.value, "overall_score": float(audit.overall_score)}
        self._persist_jsonl(self.ethics_log_path, {"timestamp": datetime.datetime.now().isoformat(), "audit": res})
        return res

    def _compute_risk_assessment(self, confidence: float, ethics_audit: dict) -> dict:
        score = 1.0 - confidence
        level = "high" if score > 0.7 else "medium" if score > 0.4 else "low"
        return {"risk_score": score, "risk_level": level}

    def _apply_safety_gate(self, answer_text: str) -> tuple[str, dict, dict]:
        conf = self._estimate_confidence_from_docs()
        audit = self._audit_answer(answer_text)
        risk = self._compute_risk_assessment(conf, audit)
        return answer_text, audit, risk

    def _recall_memories(self):
        try:
            mems = self.memory_manager.search_memories(self.question)
            if mems: self.state["memories"] = mems
        except: pass

    def approve_answer(self):
        if not self.current_answer_draft: return
        self.log_data["final_answer"] = self.current_answer_draft
        self.finished = True
        save_history(self.log_data)

    def _detect_loop(self) -> bool:
        """直近3ステップが同一アクションならループと判定し、クエリを書き換えて再計画する。"""
        if len(self.log_data["trace"]) < 3:
            return False
        last_actions = [t["action"] for t in self.log_data["trace"][-3:]]
        if len(set(last_actions)) != 1:
            return False
        # ループ検出: クエリを書き換えて再試行
        logger.warning(f"Loop detected (action={last_actions[0]}), attempting query rewrite.")
        try:
            rewrite_prompt = (
                f"以下の質問を別の角度から書き換えてください。書き換え後の質問のみを返してください。\n\n質問: {self.question}"
            )
            rewritten = call_llm(rewrite_prompt, model=self.llm_model)
            if rewritten and not rewritten.startswith("Error") and rewritten.strip() != self.question:
                logger.info(f"Query rewritten: {rewritten.strip()[:80]}")
                self.question = rewritten.strip()
                self.state["question"] = self.question
                # ループ判定をリセットするためトレースの末尾を削除
                self.log_data["trace"] = self.log_data["trace"][:-3]
                return False
        except Exception as exc:
            logger.warning(f"Query rewrite failed: {exc}")
        return True

    def _handle_max_steps_reached(self):
        self.finished = True
        return {"action": "stop", "result": "Max steps reached"}

    def _plan_action(self):
        docs_summary = self._get_docs_summary()
        # 直近5ステップの行動履歴を文字列化してプランナーに渡す
        recent_trace = self.log_data["trace"][-5:]
        action_history = "\n".join(
            f"step{t['step']}: action={t['action']} result={str(t.get('result',''))[:80]}"
            for t in recent_trace
        )
        prompt = PLAN_PROMPT.format(
            chat_history="", tools_description=self.tools_description, tool_names=self.tool_names,
            question=self.question, num_docs=len(self.state["current_docs"]),
            action_history=action_history, docs_summary=docs_summary
        )
        res = call_llm(prompt, model=self.llm_model)
        from .utils import safe_json_loads
        return safe_json_loads(res)

    def _handle_search_doc(self, query=None):
        q = query or self.question
        
        # キャッシュチェック
        cached_docs = self.cache_optimizer.get(q, namespace="search_doc")
        if cached_docs:
            logger.info(f"Cache Hit (L2) for query: {q}")
            self.state["current_docs"] = cached_docs
            return f"Found {len(cached_docs)} docs (from cache)."

        docs = self.retriever.hybrid_search(q, top_k=self.retrieval_top_k)
        reranked = self.reranker.rerank(q, docs, top_k=self.rerank_top_k)
        self.state["current_docs"] = reranked
        
        # キャッシュ保存
        self.cache_optimizer.set(q, reranked, namespace="search_doc")
        return f"Found {len(self.state['current_docs'])} docs."

    def _handle_search_web(self, query=None):
        q = query or self.question
        # 相対日付の検出と正規化（例: '昨日' -> '2026-05-16'）
        try:
            normalized_q, interpreted_date = parse_relative_date(q)
            if interpreted_date:
                logger.info(f"Interpreted relative date for query: {interpreted_date}")
                q = normalized_q
                # 記録して UI/ログで表示できるようにする
                self.state["interpreted_date"] = interpreted_date
        except Exception:
            # パーサ失敗は致命的ではないのでログに留める
            logger.debug("Date parsing failed or not available for query")
        
        # キャッシュチェック
        cached_docs = self.cache_optimizer.get(q, namespace="search_web")
        if cached_docs:
            logger.info(f"Cache Hit (L2) for web query: {q}")
            self.state["current_docs"] = cached_docs
            return f"Web search found {len(cached_docs)} docs (from cache)."

        docs = search_web_tool(q)
        reranked = self.reranker.rerank(q, docs)
        self.state["current_docs"] = reranked
        
        # キャッシュ保存
        self.cache_optimizer.set(q, reranked, namespace="search_web")
        return f"Web search found {len(docs)} docs."

    def _handle_answer(self, thought):
        docs_summary = self._get_docs_summary()
        prompt = ANSWER_PROMPT.format(original_question=self.question, docs=docs_summary)
        self.current_answer_draft = call_llm(prompt, model=self.llm_model)
        return "Answer generated."

    def _handle_write_file(self, path: str, content: str) -> str:
        try:
            with open(path, "w", encoding="utf-8") as f: f.write(content)
            return f"File written: {path}"
        except Exception as e: return str(e)

    def _handle_run_shell(self, command: str) -> str:
        """シェルコマンドを安全に実行する。shell=Trueは使用しない。"""
        import shlex
        try:
            # shell=True はコマンドインジェクションのリスクがあるため禁止
            args = shlex.split(command)
            res = subprocess.check_output(args, shell=False, text=True, timeout=30)
            return res
        except Exception as e:
            return str(e)

    def _get_docs_summary(self):
        return "\n".join([f"[{d.get('id')}] {d.get('text', '')[:200]}" for d in self.state["current_docs"]]) or "No docs."

    def run_step(self):
        if self.finished: return
        self.step_count += 1
        if self._detect_loop(): return
        if self.step_count > self.max_steps:
            self._handle_max_steps_reached()
            return

        start_time = time.time()
        success = False
        action = "unknown"
        try:
            # 前処理: 相対日付を検出したら自動で web 検索を実行して docs を注入する
            try:
                if os.getenv("RAG_ENABLE_DATE_PRESEARCH", "true").lower() == "true":
                    norm_q, interpreted_date = parse_relative_date(self.question)
                    if interpreted_date:
                        logger.info(f"Auto-presearch due to interpreted date: {interpreted_date}")
                        self.state["interpreted_date"] = interpreted_date
                        # キャッシュ優先で検索実行
                        cached = self.cache_optimizer.get(norm_q, namespace="search_web")
                        if cached:
                            self.state["current_docs"] = cached
                        else:
                            docs = search_web_tool(norm_q)
                            reranked = self.reranker.rerank(norm_q, docs)
                            self.state["current_docs"] = reranked
                            self.cache_optimizer.set(norm_q, reranked, namespace="search_web")
                        # ログに残す
                        self._log_trace("preprocess", "auto_search_web", f"Auto searched web for date {interpreted_date}")
            except Exception:
                logger.debug("Date presearch disabled or failed")

            plan = self._plan_action()
            if not plan: return
            
            action = plan.get("action", "answer")
            thought = plan.get("thought", "")
            tool_input = plan.get("tool_input", {})

            # Security Check
            if action in ["search_doc", "search_web"]:
                q = tool_input.get("query", self.question)
                mask = self.security_manager.mask_pii(q)
                if mask["pii_count"] > 0: logger.info(f"PII Masked: {mask['masked']}")

            # Reliability Wrap (Circuit Breaker + Retry)
            def execute_action():
                if action == "search_doc": return self._handle_search_doc(tool_input.get("query"))
                elif action == "search_web": return self._handle_search_web(tool_input.get("query"))
                elif action == "answer":
                    res = self._handle_answer(thought)
                    self.finished = True
                    return res
                else: return f"Unknown action: {action}"

            res = self.circuit_breaker.call(
                self.retry_manager.execute,
                execute_action
            )
            success = True
            self._log_trace(thought, action, res, plan)

        except Exception as e:
            res = f"Action failed after retries: {e}"
            logger.error(res)
            self._log_trace("System", "error", res)
            success = False
        finally:
            duration = time.time() - start_time
            self.sla_monitor.record_request(duration, success)
            # 実行経験を自己改善エンジンに記録
            try:
                self._self_improvement.record_experience(
                    task=self.question[:80],
                    action=action,
                    result=success,
                    execution_time=duration,
                    context={"step": self.step_count, "model": self.llm_model},
                )
            except Exception:
                pass

    def _log_trace(self, thought, action, result, debug_info=None):
        self.log_data["trace"].append({
            "step": self.step_count, "thought": thought, "action": action, "result": result, "debug_info": debug_info
        })

def run_agent(question):
    retriever = Retriever()
    reranker = Reranker()
    agent = RAGAgent(question, retriever, reranker)
    while not agent.finished:
        agent.run_step()
    return agent.log_data.get("final_answer")