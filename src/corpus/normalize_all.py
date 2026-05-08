import os
from pathlib import Path
from .normalize import normalize_text

# ============================================================
# STEP 0: パス設定
#   - プロジェクトルートを基準に、入出力ディレクトリを定義
# ============================================================
ROOT = Path(__file__).resolve().parents[2]
from src.utils.path_utils import get_corpus_path

CORPUS_ROOT = get_corpus_path()
PAGES_DIR = CORPUS_ROOT / "pages"        # 入力: OCR済みテキスト (ページごと)
OUT_DIR = CORPUS_ROOT / "normalized"     # 出力: 正規化・結合済みテキスト (1冊1ファイル)

# ---------------------------------------------------------
# 1冊分を正規化する
# ---------------------------------------------------------
def normalize_book(book_id: str):
    """
    指定されたブックID (ディレクトリ) 内の全ページを読み込み、
    正規化処理を適用してから1つのテキストファイルに結合して保存します。
    """
    print(f"[INFO] Normalizing {book_id}")

    # 1. 入力ディレクトリと出力ファイルパスの決定
    book_dir = PAGES_DIR / book_id
    out_path = OUT_DIR / f"{book_id}.txt"

    texts = []

    # 2. ページファイルの取得とソート
    #    page_001.txt, page_002.txt ... の順に処理するため sorted が必須
    if not book_dir.exists():
        print(f"[WARN] Directory not found: {book_dir}")
        return

    files = sorted(list(book_dir.glob("*.txt")))
    if not files:
        print(f"[WARN] No text files found in {book_dir}")
        return

    # 3. 各ページを正規化
    for page_path in files:
        try:
            with open(page_path, "r", encoding="utf-8") as f:
                raw = f.read()
        except Exception as e:
            print(f"[ERROR] Failed to read {page_path}: {e}")
            continue

        # 正規化処理の適用 (normalize.py)
        norm = normalize_text(raw)

        # 空ページはスキップ (ノイズのみのページなど)
        if norm.strip():
            texts.append(norm)

    # 4. 全ページを結合して保存
    #    LLM学習用には、ページ区切りを明確にするより文章として繋げることが多いが、
    #    ここでは念のため改行2つで区切って結合する
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(texts))

    print(f"  -> Saved {len(texts)} pages to: {out_path.name}")


# ---------------------------------------------------------
# 全冊を正規化する
# ---------------------------------------------------------
def normalize_all():
    print(f"Start normalizing all books from {PAGES_DIR} ...")

    if not PAGES_DIR.exists():
        print(f"[WARN] Directory not found: {PAGES_DIR}. Skipping normalization.")
        return

    # corpus/pages/ 配下のディレクトリ (book_001, book_002...) を取得
    # ファイルではなくディレクトリのみを対象とする
    book_dirs = sorted([d for d in PAGES_DIR.iterdir() if d.is_dir()])

    for book_dir in book_dirs:
        # ディレクトリ名 (book_001) をIDとして渡す
        normalize_book(book_dir.name)

    print("\nAll books normalized.")


# ---------------------------------------------------------
# 実行
# ---------------------------------------------------------
if __name__ == "__main__":
    normalize_all()