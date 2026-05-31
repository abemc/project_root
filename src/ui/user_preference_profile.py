from __future__ import annotations

from typing import Dict, List
import re


def infer_response_preferences(messages: List[dict], max_user_messages: int = 12) -> Dict[str, str]:
    """Infer lightweight response preferences from recent user messages.

    Session-only heuristic profile; no sensitive attribute inference.
    """
    user_texts = [str(m.get("content") or "") for m in messages if m.get("role") == "user"]
    user_texts = user_texts[-max_user_messages:]

    if not user_texts:
        return {
            "verbosity": "balanced",
            "format": "paragraph",
            "focus": "balanced",
            "validation": "normal",
        }

    concise_score = 0
    detailed_score = 0
    list_score = 0
    impl_score = 0
    explain_score = 0
    validate_score = 0

    for text in user_texts:
        t = text.lower()

        if re.search(r"簡潔|短く|要点だけ|一言|結論だけ|手短", t):
            concise_score += 2
        if re.search(r"詳しく|丁寧|具体例|深掘り|背景も|初心者向け", t):
            detailed_score += 2

        if re.search(r"箇条書き|リスト|手順|ステップ|番号で|順番", t):
            list_score += 2

        if re.search(r"実装|修正|直して|進めて|やって|コミット|push", t):
            impl_score += 2
        if re.search(r"なぜ|理由|背景|説明して|比較", t):
            explain_score += 2

        if re.search(r"テスト|検証|e2e|回帰|動作確認", t):
            validate_score += 2

    verbosity = "balanced"
    if concise_score >= detailed_score + 2:
        verbosity = "concise"
    elif detailed_score >= concise_score + 2:
        verbosity = "detailed"

    fmt = "bullet" if list_score >= 2 else "paragraph"

    focus = "balanced"
    if impl_score >= explain_score + 2:
        focus = "implementation"
    elif explain_score >= impl_score + 2:
        focus = "explanation"

    validation = "high" if validate_score >= 2 else "normal"

    return {
        "verbosity": verbosity,
        "format": fmt,
        "focus": focus,
        "validation": validation,
    }


def build_response_style_directive(profile: Dict[str, str]) -> str:
    """Build a short directive block for LLM prompt style control."""
    if not profile:
        return ""

    lines = ["【応答スタイル調整（会話履歴推定）】"]

    verbosity = profile.get("verbosity", "balanced")
    if verbosity == "concise":
        lines.append("- 回答は要点先行で簡潔に。冗長な前置きを避ける。")
    elif verbosity == "detailed":
        lines.append("- 回答は丁寧に。必要な前提・背景を省略しすぎない。")

    fmt = profile.get("format", "paragraph")
    if fmt == "bullet":
        lines.append("- 可能な限り箇条書きまたは番号付き手順で提示する。")

    focus = profile.get("focus", "balanced")
    if focus == "implementation":
        lines.append("- 説明より実行可能な手順・コード提案を優先する。")
    elif focus == "explanation":
        lines.append("- 実装前に判断理由や比較ポイントを短く明示する。")

    validation = profile.get("validation", "normal")
    if validation == "high":
        lines.append("- 提案後に最小限の検証手順（テスト/確認）を添える。")

    if len(lines) == 1:
        return ""
    return "\n".join(lines) + "\n\n"
