import time
import sys
from pathlib import Path

# Patch for torchao compatibility (torchao 0.16.0+ requires torch 2.5+, but we have 2.4.1)
import torch
if not hasattr(torch, "int1"):
    for i in range(1, 8):
        for dtype in [f"int{i}", f"uint{i}"]:
            setattr(torch, dtype, type(dtype, (), {})())

# このスクリプトの場所を基準にプロジェクトルートをsys.pathに追加
# これにより、`src`パッケージ内のモジュールを正しくインポートできる
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

# 各ステップの処理をインポート
from src.corpus.process_all_pdfs import process_all_pdfs
from src.corpus.normalize_all import normalize_all
from src.corpus.create_dataset import create_dataset
from src.embeddings.embedding import generate_embeddings

def main():
    """
    知識ベース構築の全パイプラインを実行する。
    1. PDFからテキストを抽出
    2. テキストをチャンク化し、データセットを作成
    3. 埋め込みベクトルを生成
    4. FAISSインデックスを構築
    """
    start_time = time.time()

    print("--- STEP 1: PDF処理 (GPU使用: OCR/翻訳/正規化) ---")
    process_all_pdfs()
    normalize_all()
    print("\n--- STEP 1完了 ---\n")

    print("--- STEP 2: テキストをチャンク化し、データセットを作成 ---")
    create_dataset()
    print("\n--- STEP 2完了 ---\n")

    print("--- STEP 3: 埋め込みベクトルを生成 ---")
    generate_embeddings()
    print("\n--- STEP 3完了 ---\n")

    end_time = time.time()
    total_time = end_time - start_time
    print(f"知識ベースの構築が完了しました。")
    print(f"合計所要時間: {total_time:.2f} 秒")

if __name__ == "__main__":
    main()