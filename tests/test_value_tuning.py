from src.self_improvement.feedback_manager import FeedbackManager
from src.self_improvement.value_tuning import aggregate_value_signals, infer_value_signals


def test_infer_value_signals_from_tags_and_feedback_text():
    signals = infer_value_signals(
        tags=["正確性", "出典明示", "安全性"],
        feedback_text="とても正確で、安全面の配慮もあり、出典が明確で良い",
        metadata={},
    )

    assert signals["accuracy"] >= 0.5
    assert signals["safety"] >= 0.5
    assert signals["transparency"] >= 0.5


def test_aggregate_value_signals_returns_means_and_counts():
    summary = aggregate_value_signals(
        [
            {
                "tags": ["正確性", "わかりやすさ"],
                "feedback": "正確でわかりやすい",
                "metadata": {},
            },
            {
                "tags": ["安全性", "中立性"],
                "feedback": "安全で偏りが少ない",
                "metadata": {},
            },
        ]
    )

    assert summary["total_items"] == 2
    assert summary["signal_counts"]["accuracy"] >= 1
    assert summary["signal_counts"]["safety"] >= 1
    assert 0.0 <= summary["signal_means"]["accuracy"] <= 1.0


def test_feedback_manager_records_value_signals_and_summary(tmp_path):
    mgr = FeedbackManager(storage_dir=str(tmp_path / "feedback"))
    fb = mgr.record_feedback(
        user_query="テスト質問",
        model_response="テスト回答",
        rating=0.9,
        feedback_text="とても正確でわかりやすい回答でした",
        tags=["正確性", "わかりやすさ", "有用性"],
    )

    value_signals = fb.metadata.get("value_signals") or {}
    assert value_signals["accuracy"] >= 0.5
    assert value_signals["clarity"] >= 0.5
    assert value_signals["helpfulness"] >= 0.5

    exported = mgr.export_for_training(min_rating=0.0)
    assert exported[0]["value_signals"]["accuracy"] >= 0.5

    summary = mgr.get_value_tuning_summary(min_rating=0.0)
    assert summary["signal_means"]["accuracy"] >= 0.5


def test_infer_value_signals_uses_ethics_metadata_for_safety():
    allow_signals = infer_value_signals(
        tags=[],
        feedback_text=None,
        metadata={"ethics": {"action": "allow", "confidence": 0.9}},
    )
    warn_signals = infer_value_signals(
        tags=[],
        feedback_text=None,
        metadata={"ethics": {"action": "warn", "confidence": 0.8}},
    )
    block_signals = infer_value_signals(
        tags=[],
        feedback_text=None,
        metadata={"ethics": {"action": "block", "confidence": 0.95}},
    )

    assert allow_signals["safety"] > warn_signals["safety"]
    assert warn_signals["safety"] > block_signals["safety"]
