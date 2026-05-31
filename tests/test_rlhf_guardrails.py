import json

from src.self_improvement.feedback_manager import FeedbackManager
from src.self_improvement import integration as rlhf_integration


def test_feedback_manager_records_traceability_metadata(tmp_path):
    mgr = FeedbackManager(storage_dir=str(tmp_path / "feedback"))

    fb = mgr.record_feedback(
        user_query="テスト質問",
        model_response="テスト回答",
        rating=0.8,
        tags=["有用性"],
        response_id="resp-123",
        model_name="qwen2.5:7b",
        prompt_version="v1.2.0",
        metadata={"source": "ui"},
    )

    assert fb.response_id == "resp-123"
    assert fb.model_name == "qwen2.5:7b"
    assert fb.prompt_version == "v1.2.0"
    assert fb.query_hash and len(fb.query_hash) == 16
    assert fb.metadata.get("source") == "ui"

    exported = mgr.export_for_training(min_rating=0.0)
    assert exported and exported[0]["response_id"] == "resp-123"


def test_apply_reward_adjustments_skips_when_gate_not_met(tmp_path):
    agg_path = tmp_path / "agg.json"
    agg_path.write_text(
        json.dumps(
            {
                "total_entries": 3,
                "csat_mean": 2.5,
                "nps_mean": -2,
                "adoption_rate": 0.1,
            }
        ),
        encoding="utf-8",
    )

    res = rlhf_integration.apply_reward_adjustments(str(agg_path), min_entries=20)
    assert res["status"] == "skipped"
    assert any("insufficient_entries" in r for r in res["reasons"])


def test_apply_reward_adjustments_updates_config_when_gate_met(tmp_path, monkeypatch):
    agg_path = tmp_path / "agg.json"
    agg_path.write_text(
        json.dumps(
            {
                "total_entries": 50,
                "csat_mean": 4.2,
                "nps_mean": 7,
                "adoption_rate": 0.7,
            }
        ),
        encoding="utf-8",
    )

    saved = {}

    class DummyConfig:
        def load_config(self):
            return {"reward_weights": {"csat": 1.0, "nps": 1.0, "adoption": 1.0}}

        def save_config(self, conf):
            saved.update(conf)

    monkeypatch.setattr(rlhf_integration, "RAGAgentConfig", DummyConfig)

    res = rlhf_integration.apply_reward_adjustments(str(agg_path), min_entries=20)
    assert res["status"] == "ok"
    assert "weights" in res
    assert "reward_weights" in saved
    assert set(saved["reward_weights"].keys()) == {"csat", "nps", "adoption"}
