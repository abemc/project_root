import json
import os
from types import MethodType
from unittest.mock import MagicMock

from autonomous_rag_agent import AutonomousRAGAgent


def test_compute_risk_assessment_high_risk():
    agent = AutonomousRAGAgent.__new__(AutonomousRAGAgent)

    result = agent._compute_risk_assessment(
        confidence=0.10,
        ethics_audit={
            "status": "fail",
            "overall_score": 0.10,
        },
    )

    assert result["risk_level"] == "high"
    assert result["risk_score"] >= 0.75


def test_query_blocks_answer_on_strict_high_risk():
    agent = AutonomousRAGAgent.__new__(AutonomousRAGAgent)
    agent.config = {
        "search_method": "ハイブリッド",
        "llm_model": "qwen2.5:7b",
        "top_k": 1,
    }

    def _search_corpus(self, question, top_k):
        return [{"id": "doc1", "score": 0.0, "text": "dummy", "meta": {"source": "docA"}}]

    def _format_sources(self, docs):
        return [{"name": "docA", "category": "knowledge_base", "path": "corpus/corpus_meta.json", "score": 0.0, "text": "dummy"}]

    def _generate_answer_with_llm(self, question, sources):
        return "raw_answer", "llm"

    def _audit_answer(self, question, answer, sources):
        return {
            "enabled": True,
            "status": "pass",
            "overall_score": 0.95,
            "violations": [],
            "transparency_score": 0.9,
        }

    def _compute_risk_assessment(self, confidence, ethics_audit):
        return {
            "risk_score": 0.91,
            "risk_level": "high",
            "confidence_risk": 0.9,
            "ethics_risk": 0.1,
            "ethics_status": "pass",
        }

    def _build_ethics_block_message(self, ethics_audit):
        return "BLOCKED_BY_STRICT"

    agent._search_corpus = MethodType(_search_corpus, agent)
    agent._format_sources = MethodType(_format_sources, agent)
    agent._generate_answer_with_llm = MethodType(_generate_answer_with_llm, agent)
    agent._audit_answer = MethodType(_audit_answer, agent)
    agent._compute_risk_assessment = MethodType(_compute_risk_assessment, agent)
    agent._build_ethics_block_message = MethodType(_build_ethics_block_message, agent)

    response = agent.query("test question", strict_ethics=True)

    assert response["answer"] == "BLOCKED_BY_STRICT"
    assert response["risk_assessment"]["risk_level"] == "high"
    assert response["needs_human_review"] is True
    assert response["execution_trace"][-1]["action"] == "risk_gate"
    assert response["execution_trace"][-1]["result"] == "blocked"


def test_response_log_rotation_when_size_exceeded(tmp_path):
    agent = AutonomousRAGAgent.__new__(AutonomousRAGAgent)
    agent.response_log_path = tmp_path / "agent_responses.jsonl"
    agent.log_max_bytes = 1
    agent.log_backup_count = 2

    agent._persist_response_log({"n": 1, "msg": "first"})
    agent._persist_response_log({"n": 2, "msg": "second"})

    rotated = tmp_path / "agent_responses.jsonl.1"
    assert agent.response_log_path.exists()
    assert rotated.exists()
    assert rotated.read_text(encoding="utf-8").strip() != ""


# ---------------------------------------------------------------------------
# get_ethics_report 構造テスト
# ---------------------------------------------------------------------------

def test_get_ethics_report_disabled_when_no_monitor():
    """EthicsMonitor が None のとき enabled=False を返す。"""
    agent = AutonomousRAGAgent.__new__(AutonomousRAGAgent)
    agent.ethics_monitor = None

    report = agent.get_ethics_report(period_hours=24)

    assert report["enabled"] is False
    assert "message" in report


def test_get_ethics_report_has_required_keys_when_enabled(tmp_path):
    """EthicsMonitor が有効なとき enabled/log_path を含むレポートを返す。"""
    agent = AutonomousRAGAgent.__new__(AutonomousRAGAgent)
    agent.ethics_log_path = tmp_path / "ethics_audit.jsonl"

    mock_monitor = MagicMock()
    mock_monitor.get_ethics_report.return_value = {
        "total_responses": 10,
        "violations": [],
        "pass_rate": 1.0,
    }
    agent.ethics_monitor = mock_monitor

    report = agent.get_ethics_report(period_hours=12)

    assert report["enabled"] is True
    assert "log_path" in report
    assert report["total_responses"] == 10
    mock_monitor.get_ethics_report.assert_called_once_with(time_period_hours=12)


# ---------------------------------------------------------------------------
# 応答ログ永続化テスト
# ---------------------------------------------------------------------------

def test_save_response_log_writes_file_on_query(tmp_path):
    """save_response_log=True のとき query() が JSONL を書き出す。"""
    agent = AutonomousRAGAgent.__new__(AutonomousRAGAgent)
    agent.config = {
        "search_method": "ハイブリッド",
        "llm_model": "qwen2.5:7b",
        "top_k": 1,
    }
    agent.response_log_path = tmp_path / "agent_responses.jsonl"
    agent.log_max_bytes = 0          # ローテーション無効
    agent.log_backup_count = 0

    def _search_corpus(self, q, top_k):
        return []

    def _generate_answer_with_llm(self, q, sources):
        return "answer_text", "fallback"

    def _audit_answer(self, question, answer, sources):
        return {"enabled": False, "status": "not_available", "overall_score": None, "violations": []}

    def _compute_risk_assessment(self, confidence, ethics_audit):
        return {"risk_score": 0.2, "risk_level": "low", "confidence_risk": 0.2,
                "ethics_risk": 0.4, "ethics_status": "not_available"}

    agent._search_corpus = MethodType(_search_corpus, agent)
    agent._generate_answer_with_llm = MethodType(_generate_answer_with_llm, agent)
    agent._audit_answer = MethodType(_audit_answer, agent)
    agent._compute_risk_assessment = MethodType(_compute_risk_assessment, agent)
    # document_manager.search フォールバックを回避
    dm = MagicMock()
    dm.search.return_value = []
    agent.document_manager = dm

    agent.query("test_log_persistence", save_response_log=True)

    assert agent.response_log_path.exists()
    lines = agent.response_log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["question"] == "test_log_persistence"
    assert record["answer"] == "answer_text"


# ---------------------------------------------------------------------------
# _safe_int / env-var解析テスト
# ---------------------------------------------------------------------------

def test_safe_int_returns_default_for_invalid_value():
    assert AutonomousRAGAgent._safe_int("abc", 42) == 42
    assert AutonomousRAGAgent._safe_int(None, 10) == 10
    assert AutonomousRAGAgent._safe_int(-1, 5) == 5


def test_safe_int_returns_parsed_value_for_valid_input():
    assert AutonomousRAGAgent._safe_int("1048576", 0) == 1048576
    assert AutonomousRAGAgent._safe_int(2048, 0) == 2048


def test_log_max_bytes_reads_from_env_var(monkeypatch, tmp_path):
    """RAG_LOG_MAX_BYTES 環境変数が log_max_bytes に反映される。"""
    monkeypatch.setenv("RAG_LOG_MAX_BYTES", "1024")
    agent = AutonomousRAGAgent.__new__(AutonomousRAGAgent)
    agent.config = {"log_max_bytes": 5 * 1024 * 1024, "log_backup_count": 3}
    # __init__ ではなく手動で環境変数を適用する同等処理を呼ぶ
    agent.log_max_bytes = AutonomousRAGAgent._safe_int(
        os.environ.get("RAG_LOG_MAX_BYTES", agent.config.get("log_max_bytes", 5 * 1024 * 1024)),
        5 * 1024 * 1024,
    )
    assert agent.log_max_bytes == 1024


def test_ethics_block_message_contains_violations():
    """_build_ethics_block_message が violations を含む文面を返す。"""
    agent = AutonomousRAGAgent.__new__(AutonomousRAGAgent)
    msg = agent._build_ethics_block_message(
        {"violations": ["バイアス検出", "透明性不足"]}
    )
    assert "バイアス検出" in msg
    assert "透明性不足" in msg
    assert "安全上の理由" in msg


def test_ethics_block_message_fallback_when_no_violations():
    """violations が空でもブロックメッセージが生成される。"""
    agent = AutonomousRAGAgent.__new__(AutonomousRAGAgent)
    msg = agent._build_ethics_block_message({"violations": []})
    assert "詳細情報なし" in msg


# ---------------------------------------------------------------------------
# _estimate_confidence 境界値テスト
# ---------------------------------------------------------------------------

def test_estimate_confidence_returns_minimum_when_no_sources():
    """ソースがない場合は最低信頼度 0.10 を返す。"""
    agent = AutonomousRAGAgent.__new__(AutonomousRAGAgent)
    assert agent._estimate_confidence([]) == 0.10


def test_estimate_confidence_saturates_at_one():
    """score=1.0 かつ 5 件で最大値に近い値を返す。"""
    agent = AutonomousRAGAgent.__new__(AutonomousRAGAgent)
    sources = [{"score": 1.0}] * 5
    result = agent._estimate_confidence(sources)
    assert result == 1.0


def test_estimate_confidence_blends_source_count_and_score():
    """件数とスコアが半々でブレンドされる。"""
    agent = AutonomousRAGAgent.__new__(AutonomousRAGAgent)
    # 1件 (source_factor=0.2), score=0.8 -> 0.2*0.5 + 0.8*0.5 = 0.50
    result = agent._estimate_confidence([{"score": 0.8}])
    assert result == round((0.2 * 0.5) + (0.8 * 0.5), 2)


# ---------------------------------------------------------------------------
# _audit_answer フォールバックテスト
# ---------------------------------------------------------------------------

def test_audit_answer_returns_not_available_when_no_monitor():
    """ethics_monitor が None のとき status='not_available' を返す。"""
    agent = AutonomousRAGAgent.__new__(AutonomousRAGAgent)
    agent.ethics_monitor = None

    result = agent._audit_answer(
        question="何か？",
        answer="回答",
        sources=[],
    )

    assert result["enabled"] is False
    assert result["status"] == "not_available"
    assert result["violations"] == []
    assert result["overall_score"] is None
