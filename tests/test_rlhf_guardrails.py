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


def test_apply_reward_adjustments_uses_rlaif_blend_when_ai_is_reliable(tmp_path, monkeypatch):
    human_agg_path = tmp_path / "human_agg.json"
    human_agg_path.write_text(
        json.dumps(
            {
                "total_entries": 40,
                "csat_mean": 3.8,
                "nps_mean": 4,
                "adoption_rate": 0.5,
            }
        ),
        encoding="utf-8",
    )

    ai_agg_path = tmp_path / "ai_agg.json"
    ai_agg_path.write_text(
        json.dumps(
            {
                "total_entries": 120,
                "confidence_mean": 0.86,
                "quality_mean": 0.9,
                "nps_mean": 8,
                "adoption_rate": 0.85,
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

    res = rlhf_integration.apply_reward_adjustments(
        agg_path=str(human_agg_path),
        ai_agg_path=str(ai_agg_path),
        min_entries=20,
        ai_weight=0.4,
        min_ai_entries=30,
        min_ai_confidence=0.7,
    )

    assert res["status"] == "ok"
    assert res.get("source") == "human_ai_blended"
    assert res.get("blend_details", {}).get("ai_used") is True
    assert res.get("blend_details", {}).get("effective_ai_weight", 0) > 0
    assert "reward_weights" in saved


def test_apply_reward_adjustments_falls_back_to_human_when_ai_confidence_low(tmp_path, monkeypatch):
    human_agg_path = tmp_path / "human_agg.json"
    human_agg_path.write_text(
        json.dumps(
            {
                "total_entries": 50,
                "csat_mean": 4.0,
                "nps_mean": 6,
                "adoption_rate": 0.7,
            }
        ),
        encoding="utf-8",
    )

    ai_agg_path = tmp_path / "ai_agg.json"
    ai_agg_path.write_text(
        json.dumps(
            {
                "total_entries": 200,
                "confidence_mean": 0.30,
                "quality_mean": 0.95,
                "nps_mean": 9,
                "adoption_rate": 0.9,
            }
        ),
        encoding="utf-8",
    )

    class DummyConfig:
        def load_config(self):
            return {"reward_weights": {"csat": 1.0, "nps": 1.0, "adoption": 1.0}}

        def save_config(self, conf):
            return None

    monkeypatch.setattr(rlhf_integration, "RAGAgentConfig", DummyConfig)

    res = rlhf_integration.apply_reward_adjustments(
        agg_path=str(human_agg_path),
        ai_agg_path=str(ai_agg_path),
        min_entries=20,
        ai_weight=0.4,
        min_ai_entries=30,
        min_ai_confidence=0.7,
    )

    assert res["status"] == "ok"
    assert res.get("source") == "human_only"
    assert res.get("blend_details", {}).get("ai_used") is False
    assert "low_ai_confidence" in (res.get("blend_details", {}).get("reason") or "")


def test_apply_reward_adjustments_auto_aggregates_ai_feedback_when_missing_ai_agg(tmp_path, monkeypatch):
    human_agg_path = tmp_path / "human_agg.json"
    human_agg_path.write_text(
        json.dumps(
            {
                "total_entries": 50,
                "csat_mean": 4.0,
                "nps_mean": 6,
                "adoption_rate": 0.6,
            }
        ),
        encoding="utf-8",
    )

    feedback_history_path = tmp_path / "feedback_history.jsonl"
    feedback_history_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "a1",
                        "rating": 0.7,
                        "model_name": "judge-v1",
                        "metadata": {
                            "ai_feedback": {
                                "quality": 0.8,
                                "confidence": 0.9,
                                "nps": 7,
                                "adoption_rate": 0.8,
                            }
                        },
                    }
                ),
                json.dumps(
                    {
                        "id": "a2",
                        "rating": 0.8,
                        "model_name": "judge-v1",
                        "metadata": {
                            "ai_feedback": {
                                "quality": 0.85,
                                "confidence": 0.88,
                                "nps": 8,
                                "adoption_rate": 0.82,
                            }
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    ai_agg_path = tmp_path / "ai_agg_generated.json"

    class DummyConfig:
        def load_config(self):
            return {"reward_weights": {"csat": 1.0, "nps": 1.0, "adoption": 1.0}}

        def save_config(self, conf):
            return None

    monkeypatch.setattr(rlhf_integration, "RAGAgentConfig", DummyConfig)

    res = rlhf_integration.apply_reward_adjustments(
        agg_path=str(human_agg_path),
        ai_agg_path=str(ai_agg_path),
        feedback_history_path=str(feedback_history_path),
        min_entries=20,
        ai_weight=0.3,
        min_ai_entries=1,
        min_ai_confidence=0.5,
        auto_aggregate_ai=True,
    )

    assert res["status"] == "ok"
    assert ai_agg_path.exists()
    assert res.get("auto_ai_aggregate") is not None
    assert res.get("source") == "human_ai_blended"
