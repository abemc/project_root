import re
from typing import List
import tiktoken

MAX_TOKENS = 450
MIN_TOKENS = 250
OVERLAP_SENTENCES = 3

enc = tiktoken.get_encoding("cl100k_base")

# ============================================================
# 1. セクション境界の検出（強化版）
# ============================================================
SECTION_PATTERNS = r"""(?m)^(
    第[0-9一二三四五六七八九十]+章 |
    第[0-9一二三四五六七八九十]+節 |
    [0-9]+\.[0-9]+\.[0-9]+(?:\.[0-9]+)*\s+.+ |
    [0-9]+\.[0-9]+\s+.+ |
    序章|はじめに|まとめ|付録 |
    定義|例題|問題|命題|補題|系|証明 |
    Definition|Example|Proof|Theorem|Lemma|Corollary|Remark|Note |
    図\s*[0-9]+\.[0-9]+ |
    表\s*[0-9]+\.[0-9]+
)"""

def split_by_sections(text: str) -> List[str]:
    parts = re.split(SECTION_PATTERNS, text, flags=re.VERBOSE)
    chunks = []
    for i in range(1, len(parts), 2):
        header = parts[i].strip()
        body = parts[i+1].strip()
        chunks.append(f"{header}\n{body}")
    return chunks if chunks else [text]


# ============================================================
# 2. 文分割（翻訳後日本語向け）
# ============================================================
def split_into_sentences(text: str) -> List[str]:
    # 文末記号で分割
    sentences = re.split(r"(?<=[。．.!?])\s+", text)

    # 改行2つ以上も文区切り
    final = []
    for s in sentences:
        final.extend(re.split(r"\n{2,}", s))

    # 数式中のピリオド誤爆を防ぐ
    cleaned = []
    for s in final:
        if re.match(r"^\s*$", s):
            continue
        cleaned.append(s.strip())

    return cleaned


# ============================================================
# 3. 数式・コード・キャプションの自動検出
# ============================================================
def is_formula_block(s: str) -> bool:
    if "$" in s or r"\[" in s or r"\]" in s:
        return True
    if re.search(r"[=+\-*/∑∫∞≈≒≡≤≥]", s):
        return True
    return False

def is_code_block(s: str) -> bool:
    if re.match(r"^\s*(def |class |for |while |if |else:|import )", s):
        return True
    if "{" in s and "}" in s:
        return True
    return False

def is_caption(s: str) -> bool:
    return bool(re.match(r"^(図|表)\s*[0-9]+\.[0-9]+", s))


# ============================================================
# 4. token 数を計算
# ============================================================
def count_tokens(text: str) -> int:
    return len(enc.encode(text))


# ============================================================
# 5. チャンク化本体
# ============================================================
def chunk_text(text: str) -> List[str]:
    text = text.strip()
    if not text:
        return []

    sections = split_by_sections(text)
    final_chunks = []

    for sec in sections:
        sentences = split_into_sentences(sec)

        current = []
        current_tokens = 0

        i = 0
        while i < len(sentences):
            s = sentences[i]
            s_tokens = count_tokens(s)

            # --- 数式ブロック ---
            if is_formula_block(s):
                if current:
                    final_chunks.append(" ".join(current))
                    current = []
                    current_tokens = 0
                final_chunks.append(s)
                i += 1
                continue

            # --- コードブロック ---
            if is_code_block(s):
                if current:
                    final_chunks.append(" ".join(current))
                    current = []
                    current_tokens = 0
                final_chunks.append(s)
                i += 1
                continue

            # --- キャプション ---
            if is_caption(s):
                merged = s
                if i + 1 < len(sentences):
                    merged += " " + sentences[i+1]
                    i += 1
                if current:
                    final_chunks.append(" ".join(current))
                    current = []
                    current_tokens = 0
                final_chunks.append(merged)
                i += 1
                continue

            # --- 通常文 ---
            if current_tokens + s_tokens <= MAX_TOKENS:
                current.append(s)
                current_tokens += s_tokens
            else:
                # チャンク確定
                final_chunks.append(" ".join(current))

                # オーバーラップ（文単位）
                overlap = current[-OVERLAP_SENTENCES:]
                current = overlap + [s]
                current_tokens = sum(count_tokens(x) for x in current)

            i += 1

        if current:
            final_chunks.append(" ".join(current))

    # ノイズ除去
    cleaned = []
    for c in final_chunks:
        if "copyright" in c.lower():
            continue
        cleaned.append(c)

    return cleaned