from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
from typing import List, Optional


@dataclass
class EthicsDecision:
    action: str  # allow | warn | block | escalate
    category: str
    reason: str
    confidence: float
    matched_rules: List[str]


class EthicsGuard:
    """Rule-based ethics checker for incoming user instructions."""

    BLOCK_RULES = [
        {
            "category": "violence_or_weapons",
            "reason": "危険行為・武器/爆発物関連の依頼",
            "patterns": [
                r"爆弾",
                r"爆発物",
                r"火薬",
                r"殺害",
                r"毒(物|薬)?",
                r"銃(の作り方|を作)",
            ],
        },
        {
            "category": "cyber_abuse",
            "reason": "不正アクセス・マルウェア等の悪用依頼",
            "patterns": [
                r"マルウェア",
                r"ランサムウェア",
                r"フィッシング",
                r"パスワード(を)?盗",
                r"不正アクセス",
                r"ddos",
                r"sqlインジェクション(攻撃)?",
            ],
        },
        {
            "category": "fraud_or_deception",
            "reason": "詐欺・なりすまし・偽造を助長する依頼",
            "patterns": [
                r"詐欺",
                r"なりすまし",
                r"偽造",
                r"身分証(明)?(を)?作",
                r"クレカ(情報)?(を)?盗",
            ],
        },
        {
            "category": "sexual_minor_or_hate",
            "reason": "未成年の性的内容またはヘイトを含む依頼",
            "patterns": [
                r"未成年.*(性的|わいせつ)",
                r"児童.*(性的|わいせつ)",
                r"ヘイト",
                r"差別(を)?煽",
            ],
        },
    ]

    WARN_RULES = [
        {
            "category": "sensitive_professional_advice",
            "reason": "医療・法律・投資など高リスク助言領域",
            "patterns": [
                r"診断(して|してほしい)?",
                r"処方(して|提案)",
                r"法律相談",
                r"訴訟",
                r"投資(判断|助言)",
                r"確実に儲",
            ],
        },
        {
            "category": "privacy_or_personal_data",
            "reason": "個人情報・機微情報の取り扱い",
            "patterns": [
                r"個人情報",
                r"住所(を)?特定",
                r"電話番号(を)?調べ",
                r"顔写真(から)?特定",
            ],
        },
    ]

    SAFE_CONTEXT_PATTERNS = [
        r"対策",
        r"防御",
        r"予防",
        r"検知",
        r"監査",
        r"教育",
        r"学習",
        r"ctf",
        r"セキュリティ研修",
    ]

    def __init__(self, audit_log_path: str = "logs/ethics_audit.jsonl"):
        self.audit_log_path = Path(audit_log_path)

    def evaluate(self, text: str, source: str = "chat_input") -> EthicsDecision:
        q = (text or "").strip()
        if not q:
            decision = EthicsDecision(
                action="allow",
                category="empty",
                reason="空入力",
                confidence=1.0,
                matched_rules=[],
            )
            self._audit(decision, q, source)
            return decision

        normalized = q.lower()

        for rule in self.BLOCK_RULES:
            hits = [p for p in rule["patterns"] if re.search(p, normalized, re.IGNORECASE)]
            if hits:
                # セキュリティ教育/防御文脈では、サイバー系の過剰ブロックを緩和
                if rule["category"] == "cyber_abuse":
                    safe_hits = [p for p in self.SAFE_CONTEXT_PATTERNS if re.search(p, normalized, re.IGNORECASE)]
                    if safe_hits:
                        decision = EthicsDecision(
                            action="warn",
                            category="cyber_safety_education",
                            reason="サイバー領域だが防御・教育文脈のため注意喚起で継続",
                            confidence=0.75,
                            matched_rules=hits + safe_hits,
                        )
                        self._audit(decision, q, source)
                        return decision

                decision = EthicsDecision(
                    action="block",
                    category=rule["category"],
                    reason=rule["reason"],
                    confidence=0.95,
                    matched_rules=hits,
                )
                self._audit(decision, q, source)
                return decision

        for rule in self.WARN_RULES:
            hits = [p for p in rule["patterns"] if re.search(p, normalized, re.IGNORECASE)]
            if hits:
                decision = EthicsDecision(
                    action="warn",
                    category=rule["category"],
                    reason=rule["reason"],
                    confidence=0.65,
                    matched_rules=hits,
                )
                self._audit(decision, q, source)
                return decision

        decision = EthicsDecision(
            action="allow",
            category="general",
            reason="禁止・注意ルールに一致なし",
            confidence=0.8,
            matched_rules=[],
        )
        self._audit(decision, q, source)
        return decision

    def _audit(self, decision: EthicsDecision, query: str, source: str) -> None:
        try:
            self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
            query_hash = hashlib.sha256(query.encode("utf-8", errors="ignore")).hexdigest()[:16]
            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": source,
                "query_hash": query_hash,
                "query_preview": query[:120],
                "decision": asdict(decision),
            }
            with self.audit_log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            # Audit logging must not break user interaction.
            pass
