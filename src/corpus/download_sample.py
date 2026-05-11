import requests
from pathlib import Path

# プロジェクトルートの特定
ROOT = Path(__file__).resolve().parents[2]
# PDF配置先: project_root/corpus/raw_pdfs
from src.utils.path_utils import get_corpus_path

CORPUS_ROOT = get_corpus_path()
PDF_DIR = CORPUS_ROOT / "raw_pdfs"

def download_sample_pdf():
    # ディレクトリ作成
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    
    # サンプルとして "Attention Is All You Need" の論文を使用
    url = "https://arxiv.org/pdf/1706.03762.pdf"
    filename = "attention_is_all_you_need.pdf"
    output_path = PDF_DIR / filename
    
    print(f"Downloading sample PDF to: {output_path} ...")
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        with open(output_path, "wb") as f:
            f.write(response.content)
        
        print("Download successful!")
        print("You can now run: python -m src.corpus.pdf_converter")
        
    except Exception as e:
        print(f"Failed to download: {e}")

if __name__ == "__main__":
    download_sample_pdf()