from src.ui.user_preference_profile import (
    build_response_style_directive,
    infer_response_preferences,
)


def test_infer_prefers_concise_implementation_and_validation():
    messages = [
        {"role": "user", "content": "簡潔に要点だけ。実装まで進めてください。"},
        {"role": "user", "content": "テストと回帰確認もお願いします。"},
    ]
    prof = infer_response_preferences(messages)

    assert prof["verbosity"] == "concise"
    assert prof["focus"] == "implementation"
    assert prof["validation"] == "high"


def test_infer_prefers_detailed_and_bullet_when_requested():
    messages = [
        {"role": "user", "content": "初心者向けに詳しく、手順を箇条書きで説明して"},
    ]
    prof = infer_response_preferences(messages)

    assert prof["verbosity"] == "detailed"
    assert prof["format"] == "bullet"


def test_build_directive_returns_empty_for_balanced_profile():
    directive = build_response_style_directive(
        {"verbosity": "balanced", "format": "paragraph", "focus": "balanced", "validation": "normal"}
    )
    assert directive == ""


def test_build_directive_contains_adjustment_lines():
    directive = build_response_style_directive(
        {"verbosity": "concise", "format": "bullet", "focus": "implementation", "validation": "high"}
    )
    assert "応答スタイル調整" in directive
    assert "簡潔" in directive
    assert "箇条書き" in directive
    assert "検証手順" in directive
