from types import SimpleNamespace

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
        return False

    def info(self, *args, **kwargs):
        return None

    def success(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def error(self, *args, **kwargs):
        return None

    def json(self, *args, **kwargs):
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
        return [SimpleNamespace(timestamp="2026-05-31T16:45:29.916267")]


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
