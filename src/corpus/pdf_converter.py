from pathlib import Path
from src.utils.path_utils import get_corpus_path, get_normalized_path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("PyMuPDF is not installed. Please run 'pip install PyMuPDF'")
    fitz = None

# --- 定数 ---
# プロジェクトルートを特定 (src/corpus/pdf_converter.py から見て2つ上)
ROOT = Path(__file__).resolve().parents[2]

# PDFが置かれているディレクトリ
CORPUS_ROOT = get_corpus_path()
PDF_DIR = CORPUS_ROOT / "raw_pdfs"
# テキストの出力先ディレクトリ
NORMALIZED_DIR = get_normalized_path()


def convert_pdf_to_text(pdf_path: Path) -> str:
    """
    単一のPDFファイルからテキストを抽出する。
    """
    if not fitz:
        raise ImportError("PyMuPDF is not installed.")

    text = ""
    try:
        doc = fitz.open(pdf_path)
        print(f"  - Processing '{pdf_path.name}', {len(doc)} pages...")
        for page in doc:
            text += page.get_text()
        doc.close()
    except Exception as e:
        print(f"  [Error] Failed to process {pdf_path.name}: {e}")
        return ""
    return text


def main():
    """
    PDF_DIR 内のすべてのPDFファイルをテキストに変換し、NORMALIZED_DIR に保存する。
    """
    if not fitz:
        return

    # 出力ディレクトリを作成
    NORMALIZED_DIR.mkdir(exist_ok=True)
    PDF_DIR.mkdir(exist_ok=True)

    print(f"Searching for PDF files in '{PDF_DIR}'...")

    # 拡張子が小文字(.pdf)と大文字(.PDF)の両方を検索
    pdf_files = sorted(list(set(list(PDF_DIR.glob("*.pdf")) + list(PDF_DIR.glob("*.PDF")))))

    if not pdf_files:
        print(f"No PDF files found in '{PDF_DIR}'.")
        if PDF_DIR.exists():
            print("Directory contents:")
            for f in PDF_DIR.iterdir():
                print(f"  - {f.name}")
        return

    for pdf_path in pdf_files:
        # 出力先のファイルパスを決定 (e.g., my_doc.pdf -> my_doc.txt)
        output_txt_path = NORMALIZED_DIR / f"{pdf_path.stem}.txt"

        print(f"Converting '{pdf_path.name}' to text...")
        extracted_text = convert_pdf_to_text(pdf_path)

        if extracted_text:
            with open(output_txt_path, "w", encoding="utf-8") as f:
                f.write(extracted_text)
            print(f"  -> Saved text to '{output_txt_path}'")

    print("\nPDF conversion process finished.")
    print("Next, please run the chunking and indexing scripts to update your knowledge base.")


if __name__ == "__main__":
    main()