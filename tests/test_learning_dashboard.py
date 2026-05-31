from types import SimpleNamespace
import json

import pandas as pd
import pytest

from src.rag import learning_dashboard as ld


class _DummyColumn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamlit:
    def __init__(self):
        self.session_state = {}
        self.metrics = []
        self.captions = []
        self.dataframes = []
        self.button_values = {}
        self.json_payloads = []
        self.success_messages = []

    def subheader(self, *args, **kwargs):
        return None

    def write(self, *args, **kwargs):
        return None

    def columns(self, n):
        return [_DummyColumn() for _ in range(n)]

    def metric(self, label, value, **kwargs):
        self.metrics.append((label, value))

    def divider(self):
        return None

    def caption(self, text):
        self.captions.append(text)

    def dataframe(self, df, **kwargs):
        self.dataframes.append(df)

    def plotly_chart(self, *args, **kwargs):
        return None

    def button(self, *args, **kwargs):
        label = args[0] if args else ""
        return bool(self.button_values.get(label, False))

    def info(self, *args, **kwargs):
        return None

    def success(self, *args, **kwargs):
        if args:
            self.success_messages.append(args[0])
        return None

    def warning(self, *args, **kwargs):
        return None

    def error(self, *args, **kwargs):
        return None

    def json(self, *args, **kwargs):
        if args:
            self.json_payloads.append(args[0])
        return None


class _DummyFeedbackManager:
    def get_value_tuning_summary(self, min_rating=0.0):
        return {
            "total_items": 216,
            "signal_means": {"accuracy": 0.75},
            "signal_counts": {"accuracy": 78},
        }

    def get_value_tuning_timeseries(self, min_rating=0.0):
        return {"timestamps": [], "signals": {}}

    def get_recent_feedback(self, n=1):
        return [
            SimpleNamespace(
                timestamp="2026-05-31T16:45:29.916267",
                user_query="アンソロピック社の概要を簡潔に説明して",
                rating=0.9,
                tags=["正確性", "有用性"],
            )
        ]


class _DummyGateLogStreamlit(_FakeStreamlit):
    def __init__(self, show_logs=True):
        super().__init__()
        self.session_state = {"rlhf_show_gate_logs": show_logs}


class _DummyNoValueTuningFeedbackManager:
    def get_value_tuning_summary(self, min_rating=0.0):
        return {"total_items": 0, "signal_means": {}, "signal_counts": {}}

    def get_value_tuning_timeseries(self, min_rating=0.0):
        return {"timestamps": [], "signals": {}}

    def get_recent_feedback(self, n=1):
        return []


class _DummyRegressionGateReport:
    def __init__(self):
        self.status = "pass"
        self.summary = {"regressed_benchmarks": 0, "improved_benchmarks": 1}
        self.notes = ["no regressions detected"]
        self.benchmark_deltas = [
            SimpleNamespace(
                benchmark_name="MMLU",
                regressions=[],
                improvements=["accuracy: +0.0400"],
            )
        ]


class _DummyRegressionGate:
    def compare(self, baseline, current):
        return _DummyRegressionGateReport()


def test_reinforcement_dashboard_shows_feedback_total_and_latest(monkeypatch):
    fake_st = _FakeStreamlit()

    monkeypatch.setattr(ld, "st", fake_st)
    monkeypatch.setattr(ld, "VALUE_TUNING_AVAILABLE", True)
    monkeypatch.setattr(ld, "RLHF_GUARD_AVAILABLE", False)
    monkeypatch.setattr(ld, "FeedbackManager", _DummyFeedbackManager)

    manager = SimpleNamespace(
        rl_manager=SimpleNamespace(decisions=[], policies=[], experience_replay=[])
    )
    dashboard = ld.LearningDashboard(manager=manager)

    dashboard._render_reinforcement_learning()

    metrics = dict(fake_st.metrics)
    assert metrics["Feedback Items"] == 216
    assert metrics["Latest Feedback"] == "2026-05-31T16:45:29.916267"
    assert "現在最も強い価値軸: accuracy (0.75)" in fake_st.captions
    assert any("Latest Feedback Summary:" in text for text in fake_st.captions)


def test_reinforcement_dashboard_runs_rlhf_update_and_shows_delta_metrics(monkeypatch):
    fake_st = _FakeStreamlit()
    fake_st.button_values["⚙️ RLHF重み更新を実行"] = True

    monkeypatch.setattr(ld, "st", fake_st)
    monkeypatch.setattr(ld, "VALUE_TUNING_AVAILABLE", False)
    monkeypatch.setattr(ld, "RLHF_GUARD_AVAILABLE", True)

    def _fake_apply_reward_adjustments(**kwargs):
        return {
            "status": "ok",
            "source": "human_ai_blended",
            "summary": {
                "csat_mean": 4.10,
                "nps_mean": 6.50,
                "adoption_rate": 0.74,
            },
            "human_summary": {
                "csat_mean": 3.90,
                "nps_mean": 6.00,
                "adoption_rate": 0.70,
            },
            "blend_details": {"ai_used": True},
        }

    monkeypatch.setattr(ld, "apply_reward_adjustments", _fake_apply_reward_adjustments)

    manager = SimpleNamespace(
        rl_manager=SimpleNamespace(decisions=[], policies=[], experience_replay=[])
    )
    dashboard = ld.LearningDashboard(manager=manager)

    dashboard._render_reinforcement_learning()

    metric_labels = [label for label, _ in fake_st.metrics]
    assert "CSAT" in metric_labels
    assert "NPS" in metric_labels
    assert "Adoption" in metric_labels
    assert any("RLHF重み更新を適用しました" in msg for msg in fake_st.success_messages)
    assert any(isinstance(payload, dict) and payload.get("status") == "ok" for payload in fake_st.json_payloads)


def test_build_gate_history_rows_includes_deltas_against_previous_run():
    logs = [
        {
            "timestamp": "2026-06-01T10:00:00",
            "status": "ok",
            "source": "human_only",
            "summary": {
                "total_entries": 120,
                "csat_mean": 4.2,
                "nps_mean": 7.0,
                "adoption_rate": 0.82,
            },
        },
        {
            "timestamp": "2026-06-01T09:00:00",
            "status": "ok",
            "source": "human_only",
            "summary": {
                "total_entries": 100,
                "csat_mean": 4.0,
                "nps_mean": 6.5,
                "adoption_rate": 0.80,
            },
        },
    ]

    rows = ld._build_gate_history_rows(logs)

    assert len(rows) == 2
    assert rows[0]["Δentries"] == 20
    assert rows[0]["Δcsat"] == pytest.approx(0.2)
    assert rows[0]["Δnps"] == pytest.approx(0.5)
    assert rows[0]["Δadoption"] == pytest.approx(0.02)
    assert rows[1]["Δentries"] is None


def test_build_gate_history_rows_handles_missing_or_non_numeric_summaries():
    logs = [
        {
            "timestamp": "2026-06-01T10:00:00",
            "status": "skipped",
            "summary": {},
        },
        {
            "timestamp": "2026-06-01T09:00:00",
            "status": "ok",
            "summary": {"total_entries": "100"},
        },
    ]

    rows = ld._build_gate_history_rows(logs)

    assert rows[0]["entries"] is None
    assert rows[0]["Δentries"] is None
    assert rows[0]["Δcsat"] is None


def test_format_gate_history_rows_formats_delta_columns():
    rows = [
        {
            "timestamp": "2026-06-01T10:00:00",
            "status": "ok",
            "source": "human_ai_blended",
            "reasons": "gate_passed",
            "entries": 120,
            "csat": 4.2,
            "nps": 7.0,
            "adoption": 0.82,
            "Δentries": 20,
            "Δcsat": 0.2,
            "Δnps": 0.5,
            "Δadoption": 0.02,
        }
    ]

    df = ld._format_gate_history_rows(rows)

    assert df.loc[0, "csat"] == "4.20"
    assert df.loc[0, "nps"] == "7.00"
    assert df.loc[0, "adoption"] == "0.82"
    assert df.loc[0, "Δcsat"] == "↑ +0.20"
    assert df.loc[0, "Δnps"] == "↑ +0.50"
    assert df.loc[0, "Δadoption"] == "↑ +0.02"


def test_reinforcement_dashboard_shows_benchmark_regression_gate(monkeypatch):
    fake_st = _FakeStreamlit()

    monkeypatch.setattr(ld, "st", fake_st)
    monkeypatch.setattr(ld, "VALUE_TUNING_AVAILABLE", False)
    monkeypatch.setattr(ld, "RLHF_GUARD_AVAILABLE", True)
    monkeypatch.setattr(ld, "REGRESSION_GATE_AVAILABLE", True)
    monkeypatch.setattr(ld, "RegressionGate", _DummyRegressionGate)
    monkeypatch.setattr(ld, "_find_recent_benchmark_results", lambda limit=2: ["current.json", "baseline.json"])

    manager = SimpleNamespace(
        rl_manager=SimpleNamespace(decisions=[], policies=[], experience_replay=[])
    )
    dashboard = ld.LearningDashboard(manager=manager)

    dashboard._render_reinforcement_learning()

    metrics = dict(fake_st.metrics)
    assert metrics["status"] == "pass"
    assert metrics["regressed"] == 0
    assert metrics["improved"] == 1
    assert any("no regressions detected" in text for text in fake_st.captions)
    assert fake_st.dataframes


def test_reinforcement_dashboard_shows_saved_regression_gate_history(monkeypatch, tmp_path):
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(ld, "st", fake_st)
    monkeypatch.setattr(ld, "VALUE_TUNING_AVAILABLE", False)
    monkeypatch.setattr(ld, "RLHF_GUARD_AVAILABLE", True)
    monkeypatch.setattr(ld, "REGRESSION_GATE_AVAILABLE", True)
    monkeypatch.setattr(ld, "RegressionGate", _DummyRegressionGate)
    monkeypatch.setattr(ld, "_find_recent_benchmark_results", lambda limit=2: ["current.json", "baseline.json"])
    monkeypatch.setattr(
        ld,
        "_read_regression_gate_reports",
        lambda limit=30: [
            {
                "status": "pass",
                "current_timestamp": "2026-06-01T10:00:00",
                "summary": {
                    "comparable_benchmarks": 1,
                    "regressed_benchmarks": 0,
                    "improved_benchmarks": 1,
                },
                "notes": ["all clear"],
            },
            {
                "status": "hold",
                "current_timestamp": "2026-06-01T09:00:00",
                "summary": {
                    "comparable_benchmarks": 1,
                    "regressed_benchmarks": 1,
                    "improved_benchmarks": 0,
                },
                "notes": ["accuracy dropped"],
            },
        ],
    )

    manager = SimpleNamespace(
        rl_manager=SimpleNamespace(decisions=[], policies=[], experience_replay=[])
    )
    dashboard = ld.LearningDashboard(manager=manager)

    dashboard._render_reinforcement_learning()

    assert any(
        isinstance(df, pd.DataFrame) and "status" in df.columns and "comparable" in df.columns
        for df in fake_st.dataframes
    )


def test_read_regression_gate_reports_and_format_rows(tmp_path, monkeypatch):
    results_dir = tmp_path / "results" / "benchmarks"
    results_dir.mkdir(parents=True)

    (results_dir / "regression_gate_20260601_100000.json").write_text(
        json.dumps(
            {
                "status": "pass",
                "current_timestamp": "2026-06-01T10:00:00",
                "summary": {
                    "comparable_benchmarks": 1,
                    "regressed_benchmarks": 0,
                    "improved_benchmarks": 1,
                },
                "notes": ["all clear"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(ld.os, "getcwd", lambda: str(tmp_path))

    records = ld._read_regression_gate_reports(limit=5)
    frame = ld._format_regression_gate_rows(records)

    assert len(records) == 1
    assert frame.loc[0, "status"] == "pass"
    assert frame.loc[0, "comparable"] == 1
    assert frame.loc[0, "regressed"] == 0


def test_read_rag_evaluation_reports_and_format_rows(tmp_path, monkeypatch):
    results_dir = tmp_path / "results" / "benchmarks"
    results_dir.mkdir(parents=True)

    (results_dir / "rag_evaluation_20260601_120000.json").write_text(
        json.dumps(
            {
                "timestamp": "2026-06-01T12:00:00",
                "summary": {
                    "total_samples": 3,
                    "average_metrics": {
                        "end_to_end_score": 0.76,
                        "factual_consistency": 0.81,
                        "rouge": 0.69,
                        "bleu": 0.58,
                    },
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(ld.os, "getcwd", lambda: str(tmp_path))

    records = ld._read_rag_evaluation_reports(limit=5)
    frame = ld._format_rag_evaluation_rows(records)

    assert len(records) == 1
    assert frame.loc[0, "samples"] == 3
    assert frame.loc[0, "end_to_end"] == 0.76
    assert frame.loc[0, "factual_consistency"] == 0.81


def test_reinforcement_dashboard_shows_saved_rag_evaluation_history(monkeypatch):
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(ld, "st", fake_st)
    monkeypatch.setattr(ld, "VALUE_TUNING_AVAILABLE", False)
    monkeypatch.setattr(ld, "RLHF_GUARD_AVAILABLE", True)
    monkeypatch.setattr(ld, "REGRESSION_GATE_AVAILABLE", True)
    monkeypatch.setattr(ld, "RegressionGate", _DummyRegressionGate)
    monkeypatch.setattr(ld, "_find_recent_benchmark_results", lambda limit=2: ["current.json", "baseline.json"])
    monkeypatch.setattr(
        ld,
        "_read_regression_gate_reports",
        lambda limit=30: [
            {
                "status": "pass",
                "current_timestamp": "2026-06-01T10:00:00",
                "summary": {
                    "comparable_benchmarks": 1,
                    "regressed_benchmarks": 0,
                    "improved_benchmarks": 1,
                },
                "notes": ["all clear"],
            }
        ],
    )
    monkeypatch.setattr(
        ld,
        "_read_rag_evaluation_reports",
        lambda limit=30: [
            {
                "timestamp": "2026-06-01T12:00:00",
                "summary": {
                    "total_samples": 3,
                    "average_metrics": {
                        "end_to_end_score": 0.76,
                        "factual_consistency": 0.81,
                        "rouge": 0.69,
                        "bleu": 0.58,
                    },
                },
                "_path": "/tmp/rag_evaluation_20260601_120000.json",
            }
        ],
    )

    manager = SimpleNamespace(
        rl_manager=SimpleNamespace(decisions=[], policies=[], experience_replay=[])
    )
    dashboard = ld.LearningDashboard(manager=manager)

    dashboard._render_reinforcement_learning()

    assert any(
        isinstance(df, pd.DataFrame) and "factual_consistency" in df.columns and "end_to_end" in df.columns
        for df in fake_st.dataframes
    )


def test_style_gate_history_rows_colors_delta_columns():
    frame = ld._format_gate_history_rows(
        [
            {
                "timestamp": "2026-06-01T10:00:00",
                "status": "ok",
                "source": "human_ai_blended",
                "reasons": "gate_passed",
                "entries": 120,
                "csat": 4.2,
                "nps": 7.0,
                "adoption": 0.82,
                "Δentries": 20,
                "Δcsat": 0.2,
                "Δnps": -0.5,
                "Δadoption": 0.0,
            }
        ]
    )

    styler = ld._style_gate_history_rows(frame)
    html = styler.to_html()

    assert "background-color: #e8f5e9" in html
    assert "background-color: #ffebee" in html
    assert "background-color: #f5f5f5" in html


def test_style_gate_history_rows_emphasizes_large_deltas():
    frame = ld._format_gate_history_rows(
        [
            {
                "timestamp": "2026-06-01T10:00:00",
                "status": "ok",
                "source": "human_ai_blended",
                "reasons": "gate_passed",
                "entries": 120,
                "csat": 4.2,
                "nps": 7.0,
                "adoption": 0.82,
                "Δentries": 20,
                "Δcsat": 0.2,
                "Δnps": -0.5,
                "Δadoption": 0.0,
            }
        ]
    )

    html = ld._style_gate_history_rows(frame).to_html()

    assert html.count("font-weight: 700") >= 2


def test_reinforcement_dashboard_handles_empty_gate_logs(monkeypatch):
    fake_st = _DummyGateLogStreamlit(show_logs=True)

    monkeypatch.setattr(ld, "st", fake_st)
    monkeypatch.setattr(ld, "VALUE_TUNING_AVAILABLE", True)
    monkeypatch.setattr(ld, "RLHF_GUARD_AVAILABLE", True)
    monkeypatch.setattr(ld, "FeedbackManager", _DummyNoValueTuningFeedbackManager)
    monkeypatch.setattr(ld, "apply_reward_adjustments", lambda **kwargs: {"status": "skipped", "summary": {}})
    monkeypatch.setattr(ld, "_read_gate_logs", lambda limit=30: [])

    manager = SimpleNamespace(
        rl_manager=SimpleNamespace(decisions=[], policies=[], experience_replay=[])
    )
    dashboard = ld.LearningDashboard(manager=manager)

    dashboard._render_reinforcement_learning()

    assert any("ログはまだありません。" in text for text in fake_st.captions)


def test_reinforcement_dashboard_renders_gate_history_with_deltas(monkeypatch):
    fake_st = _DummyGateLogStreamlit(show_logs=True)

    monkeypatch.setattr(ld, "st", fake_st)
    monkeypatch.setattr(ld, "VALUE_TUNING_AVAILABLE", True)
    monkeypatch.setattr(ld, "RLHF_GUARD_AVAILABLE", True)
    monkeypatch.setattr(ld, "FeedbackManager", _DummyNoValueTuningFeedbackManager)
    monkeypatch.setattr(ld, "apply_reward_adjustments", lambda **kwargs: {"status": "skipped", "summary": {}})
    monkeypatch.setattr(
        ld,
        "_read_gate_logs",
        lambda limit=30: [
            {
                "timestamp": "2026-06-01T10:00:00",
                "status": "ok",
                "source": "human_ai_blended",
                "reasons": ["gate_passed"],
                "summary": {
                    "total_entries": 120,
                    "csat_mean": 4.2,
                    "nps_mean": 7.0,
                    "adoption_rate": 0.82,
                },
            },
            {
                "timestamp": "2026-06-01T09:00:00",
                "status": "skipped",
                "source": "human_only",
                "reasons": ["insufficient_entries"],
                "summary": {
                    "total_entries": 100,
                    "csat_mean": 4.0,
                    "nps_mean": 6.5,
                    "adoption_rate": 0.80,
                },
            },
        ],
    )

    manager = SimpleNamespace(
        rl_manager=SimpleNamespace(decisions=[], policies=[], experience_replay=[])
    )
    dashboard = ld.LearningDashboard(manager=manager)

    dashboard._render_reinforcement_learning()

    assert any("Δ列は1つ前の実行結果との差分です。" in text for text in fake_st.captions)
    assert fake_st.dataframes
    assert any("Δcsat" in df.columns for df in fake_st.dataframes)
    assert any("Δnps" in df.columns for df in fake_st.dataframes)
    assert any("Δadoption" in df.columns for df in fake_st.dataframes)
