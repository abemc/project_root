# src/corpus/normalize.py
# ------------------------------------------------------------
# 技術書・数学書コーパス向け 正規化フィルタ
#
# 目的：
#   - 数式・コード・API名・図表キャプションなど
#     「正規化で壊れやすい情報」を一度トークンに避難させる
#   - その後、空白・改行・OCRノイズなどを安全に正規化する
#   - 最後に避難させた要素を元に戻し、意味を保った綺麗なテキストを作る
#
# この構造は LLM 学習用コーパスとして理想的。
# ------------------------------------------------------------

import re

# ============================================================
#  保護用トークン（プレースホルダ）
#  - 正規化中に壊れやすい要素を一時的に置き換えるための印
#  - §...§ という人間が読める形式で、デバッグしやすくしている
#  - 後続の処理で、インデックス付きのトークン (e.g., §INLINE_FORMULA§0) に置換される
# ============================================================
INLINE_TOKEN = "§INLINE_FORMULA§"      # $ ... $ や \( ... \) のインライン数式
DISPLAY_TOKEN = "§DISPLAY_FORMULA§"    # $$ ... $$ や \begin{equation} のディスプレイ数式
CODE_TOKEN = "§CODE_BLOCK§"            # コードブロック
CAPTION_TOKEN = "§CAPTION§"            # 図表キャプション
API_TOKEN = "§API§"                    # API 名（torch.nn.Linear など）


# ============================================================
#  STEP A-1: 数式の保護 (Protect Formulas)
# ------------------------------------------------------------
# 目的:
#   LaTeX形式の数式は、空白の削除や改行の統一といった後続の正規化処理によって
#   構文が壊れてしまう可能性が非常に高い。
#   そのため、正規化処理の前に数式全体を一つの固まりとして認識し、
#   一時的なプレースホルダトークンに置き換える（=保護する）。
# ============================================================
def protect_formulas(text: str):
    """テキスト内のLaTeX数式をプレースホルダに置き換える。"""
    # 保護した元の数式文字列を、出現順に保存するリスト
    formulas = []

    # 置換用内部関数: マッチした数式(m.group(0))をリストに保存し、
    # トークンとインデックス(例: §DISPLAY_FORMULA§0)を返す。
    def repl_display(m):
        formulas.append(m.group(0))
        return f"{DISPLAY_TOKEN}{len(formulas)-1}"

    def repl_inline(m):
        formulas.append(m.group(0))
        return f"{INLINE_TOKEN}{len(formulas)-1}"

    # 1-1. ディスプレイ数式の保護 (複数行にまたがる可能性があるため re.S フラグを使用)
    #      - $$ ... $$
    text = re.sub(r"\$\$(.+?)\$\$", repl_display, text, flags=re.S)
    #      - \[ ... \]
    text = re.sub(r"\\\[(.+?)\\\]", repl_display, text, flags=re.S)
    #      - \begin{equation} ... \end{equation}
    text = re.sub(r"\\begin\{equation\}(.+?)\\end\{equation\}", repl_display, text, flags=re.S)
    #      - \begin{align} ... \end{align}
    text = re.sub(r"\\begin\{align\}(.+?)\\end\{align\}", repl_display, text, flags=re.S)

    # 1-2. インライン数式の保護 (通常は単一行)
    #      - $ ... $ (注意: 貪欲マッチ `.+` ではなく最短マッチ `.+?` を使うことが重要)
    text = re.sub(r"\$(.+?)\$", repl_inline, text)
    #      - \( ... \)
    text = re.sub(r"\\\((.+?)\\\)", repl_inline, text)

    return text, formulas


def restore_formulas(text: str, formulas):
    """保護した数式を元のテキストに戻す。"""
    # 保護時に保存したリストを逆順にループするのが安全だが、
    # この実装ではトークンが重複しないため、順方向でも問題ない。
    for i, f in enumerate(formulas):
        # f (元の数式) にプレースホルダが含まれている可能性は低いので、
        # 単純な replace で一括置換する。
        text = text.replace(f"{DISPLAY_TOKEN}{i}", f)
        text = text.replace(f"{INLINE_TOKEN}{i}", f)
    return text


# ============================================================
#  STEP A-2: コードブロックの保護 (Protect Code Blocks)
# ------------------------------------------------------------
# 目的:
#   Pythonなどのプログラミングコードは、インデント（字下げ）が構文的に
#   重要な意味を持つ。空白の正規化によってインデントが失われると、
#   コードの意味が完全に変わってしまうため、ブロック全体を保護する。
# ============================================================
def protect_code_blocks(text: str):
    """テキスト内のコードブロックをプレースホルダに置き換える。"""
    blocks = []

    # 置換用内部関数
    def repl_fenced(m):
        blocks.append(m.group(0))
        return f"{CODE_TOKEN}{len(blocks)-1}"

    # 2-1. MarkdownのFenced Code Block (``` ... ```) を保護
    #      re.S (DOTALL) フラグで、`...` が改行を含むようにする。
    text = re.sub(r"```[\s\S]*?```", repl_fenced, text)

    # 置換用内部関数
    def repl_indented(m):
        blocks.append(m.group(0))
        return f"{CODE_TOKEN}{len(blocks)-1}"

    # 2-2. Markdownのインデント形式コードブロックを保護
    #      - (?:^|\n): 行頭または改行の直後
    #      - (    .* ... ): 4つのスペースで始まる行のグループ
    #      - (?:\n    .*)*: その後に続く「改行 + 4スペースの行」を0回以上繰り返す
    text = re.sub(r"(?:^|\n)(    .*(?:\n    .*)*)", repl_indented, text)

    return text, blocks


def restore_code_blocks(text: str, blocks):
    """保護したコードブロックを元のテキストに戻す。"""
    for i, b in enumerate(blocks):
        text = text.replace(f"{CODE_TOKEN}{i}", b)
    return text


# ============================================================
#  STEP A-3: 図表キャプションの保護 (Protect Captions)
# ------------------------------------------------------------
# 目的:
#   「図 3.2: ...」や「Table 1: ...」といったキャプションは、
#   それ自体が意味を持つ一つの単位。正規化によって改行が削除されると、
#   本文と混ざってしまう可能性があるため、行全体を保護する。
# ============================================================
def protect_captions(text: str):
    """テキスト内の図表キャプション行をプレースホルダに置き換える。"""
    captions = []

    patterns = [
        r"^(Figure\s+\d+[:.]?.*)",
        r"^(Fig\.\s*\d+[:.]?.*)",
        r"^(Table\s+\d+[:.]?.*)",
        r"^(Listing\s+\d+[:.]?.*)",
        r"^(図\s*\d+[:：]?.*)",
        r"^(表\s*\d+[:：]?.*)",
        r"^(リスト\s*\d+[:：]?.*)",
    ]

    def repl(m):
        # マッチした行全体 (m.group(1)) を保存
        captions.append(m.group(1))
        return f"{CAPTION_TOKEN}{len(captions)-1}"

    for p in patterns:
        # re.MULTILINE フラグで行頭(^)のマッチを各行の先頭で行う
        text = re.sub(p, repl, text, flags=re.MULTILINE)

    return text, captions


def restore_captions(text: str, captions):
    """保護したキャプションを元のテキストに戻す。"""
    for i, c in enumerate(captions):
        text = text.replace(f"{CAPTION_TOKEN}{i}", c)
    return text


# ============================================================
#  STEP A-4: API名などの固有名詞の保護 (Protect API Names)
# ------------------------------------------------------------
# 目的:
#   `torch.nn.Linear` や `my_func(x)` のようなAPI名や関数呼び出しは、
#   内部の `.` や `(` が他の正規化ルールに誤って解釈されるのを防ぐため保護する。
#   これらを一つのトークンとして扱うことで、意味的な一貫性を保つ。
# ============================================================
def protect_api_names(text: str):
    """テキスト内のAPI名や関数呼び出しをプレースホルダに置き換える。"""
    apis = []

    patterns = [
        r"[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_.]*",   # module.func, a.b.c
        r"[a-zA-Z_][a-zA-Z0-9_]*::[a-zA-Z_][a-zA-Z0-9_]*",  # Class::method
        r"[a-zA-Z_][a-zA-Z0-9_]*\([^\)]*\)",                # func(...)
        r"[a-zA-Z_][a-zA-Z0-9_]*<[^\>]*>",                  # Template<T>
    ]

    def repl(m):
        apis.append(m.group(0))
        return f"{API_TOKEN}{len(apis)-1}"

    for p in patterns:
        text = re.sub(p, repl, text)

    return text, apis


def restore_api_names(text: str, apis):
    """保護したAPI名を元のテキストに戻す。"""
    for i, a in enumerate(apis):
        text = text.replace(f"{API_TOKEN}{i}", a)
    return text


# ============================================================
#  STEP B: OCRノイズの除去 (Clean OCR Noise)
# ------------------------------------------------------------
# 目的:
#   PDFからのOCR結果には、見た目は似ているがUnicodeコードポイントが異なる
#   特殊文字が含まれることが多い（例: 合字 "ﬁ", 様々な種類のハイフン "−"）。
#   これらを標準的なASCII文字に統一することで、後段のLLMトークナイザが
#   扱う語彙数を削減し、埋め込み表現の一貫性を向上させる。
# ============================================================
def clean_ocr_noise(text: str) -> str:
    replacements = {
        "ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", # 合字 (Ligatures)
        "−": "-", "–": "-", "—": "-",                             # 様々なハイフン/ダッシュ
        "“": "\"", "”": "\"", "‘": "'", "’": "'",                 # 様々な引用符
        "…": "...",                                             # 三点リーダー
        "·": ".",                                               # 中点
        "×": "x",                                               # 乗算記号
        "÷": "/",                                               # 除算記号
        "\u200b": "", "\u2060": "",                              # ゼロ幅スペース
    }
    for k, v in replacements.items():
        text = text.replace(k, v)

    # 目次などで見られるリーダー線や、OCRによる類似文字のノイズ（3文字以上の連続）をスペースに置換
    text = re.sub(r'[.…_しーe]{4,}', ' ', text)

    return text


# ============================================================
#  メイン正規化関数 (normalize_text)
# ------------------------------------------------------------
# 処理フロー:
#   1. 保護 (Protect): 正規化で壊したくない要素 (数式, コード等) を
#      一時的なプレースホルダに置き換える。
#   2. 除去 (Clean): OCR由来の特殊文字などを標準化する。
#   3. 正規化 (Normalize): 改行、空白、タブなどを統一的な形式に整える。
#   4. 還元 (Restore): 保護しておいた要素を元の形に戻す。
#      このとき、保護とは逆の順序で戻すのが重要 (LIFO: Last-In, First-Out)。
# ============================================================
def normalize_text(text: str) -> str:

    # STEP 1: 壊れやすい要素を保護 (Protect)
    #         数式 -> コード -> キャプション -> API名 の順で保護する。
    #         この順序は、要素の入れ子構造を考慮して決定される。
    #         (例: キャプション内にAPI名が含まれる場合など)
    text, formulas = protect_formulas(text)
    text, code_blocks = protect_code_blocks(text)
    text, captions = protect_captions(text)
    text, apis = protect_api_names(text)

    # STEP 2: OCRノイズの除去 (Clean)
    #         保護対象以外のテキストに対して、文字レベルのクリーニングを行う。
    text = clean_ocr_noise(text)

    # STEP 3: 空白・改行の正規化 (Normalize)
    # 3-1. 改行コードをLF(\n)に統一
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # 3-2. 連続する半角スペースやタブを、1つの半角スペースに統一
    text = re.sub(r"[ \t]+", " ", text)
    # 3-3. 改行以外の不可視文字(例: \u00A0)を半角スペースに置換
    text = re.sub(r"[^\S\n]+", " ", text)

    # 3-4. 日本語文字の間に存在する不要なスペースを削除 (技術書PDFのOCRで頻出するノイズ)
    #      例: 「これ は テスト です」 -> 「これはテストです」
    text = re.sub(r"(?<=[一-龥ぁ-んァ-ンー])\s+(?=[一-龥ぁ-んァ-ンー])", "", text)

    # 3-5. テキスト全体の先頭と末尾の空白を削除
    text = text.strip()

    # STEP 4: 保護した要素を還元 (Restore)
    #         保護処理とは逆の順序 (API名 -> キャプション -> コード -> 数式) で元に戻す。
    #         これにより、入れ子になった要素が正しく復元される。
    text = restore_api_names(text, apis)
    text = restore_captions(text, captions)
    text = restore_code_blocks(text, code_blocks)
    text = restore_formulas(text, formulas)

    return text