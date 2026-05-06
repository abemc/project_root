import os
import glob
from pathlib import Path
from .extract_pdf import extract_pdf

# ============================================================
# STEP 0: プロジェクトルートを特定
#   - このファイルは src/corpus/ にあるため
#   - parents[2] で project_root を指す
# ============================================================
ROOT = Path(__file__).resolve().parents[2]

# ============================================================
# STEP 1: 入出力ディレクトリの定義
#   - raw_pdf/      : 入力PDF
#   - corpus/pages/ : OCR後のページテキスト
# ============================================================
from src.utils.path_utils import get_corpus_path

CORPUS_ROOT = get_corpus_path()
RAW_DIR = CORPUS_ROOT / "raw_pdfs"
PAGES_DIR = CORPUS_ROOT / "pages"


# ============================================================
# STEP 2: 1冊のPDFを処理する関数
#   - book_id (book_001 など) を受け取り
#   - OCR → page_001.txt, page_002.txt ... を生成
# ============================================================
def process_one_pdf(pdf_path: str, book_id: str):
    print(f"\n=== Extracting {pdf_path} ===")

    # 出力先ディレクトリ（corpus/pages/book_001）
    out_dir = PAGES_DIR / book_id
    os.makedirs(out_dir, exist_ok=True)

    # OCR 実行
    extracted_pages = extract_pdf(pdf_path, out_dir)

    print(f"Extracted: {len(extracted_pages)} pages")


# ============================================================
# STEP 3: raw_pdf 内の全PDFを処理するメイン関数
#   - book_001.pdf → book_001/
#   - book_002.pdf → book_002/
#   - という形で連番処理
# ============================================================
def process_all_pdfs():
    # raw_pdf/*.pdf をすべて取得
    pdf_files = sorted(glob.glob(str(RAW_DIR / "*.pdf")))

    if not pdf_files:
        print(f"No PDF files found in {RAW_DIR}.")
        return

    # 1冊ずつ処理
    for i, pdf_path in enumerate(pdf_files, 1):
        book_id = f"book_{i:03d}"
        process_one_pdf(pdf_path, book_id)

    print("\n=== All PDFs extracted successfully ===")


# ============================================================
# STEP 4: スクリプトとして実行された場合のエントリポイント
# ============================================================
if __name__ == "__main__":
    process_all_pdfs()