import unittest
import sys
import os

# プロジェクトルートをパスに追加して src モジュールをインポートできるようにする
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.corpus.chunk_text import (
    split_by_sections,
    split_into_sentences,
    is_formula_block,
    is_code_block,
    is_caption,
    chunk_text
)

class TestChunkText(unittest.TestCase):

    def test_is_formula_block(self):
        """数式ブロック判定のテスト"""
        self.assertTrue(is_formula_block("$$ y = ax + b $$"))
        self.assertTrue(is_formula_block(r"\[ \sum_{i=0}^N i \]"))
        self.assertTrue(is_formula_block("x = y + z"))  # 一般的な数式記号を含む
        self.assertFalse(is_formula_block("This is just a sentence."))

    def test_is_code_block(self):
        """コードブロック判定のテスト"""
        self.assertTrue(is_code_block("def my_function(args):"))
        self.assertTrue(is_code_block("class MyClass:"))
        self.assertTrue(is_code_block("if x == 1: pass"))
        self.assertTrue(is_code_block("int main() { return 0; }")) # C/C++ スタイルの波括弧
        self.assertFalse(is_code_block("This is not code."))

    def test_is_caption(self):
        """キャプション判定のテスト"""
        self.assertTrue(is_caption("図 1.1: 実験結果"))
        self.assertTrue(is_caption("表 2.3 データ一覧"))
        self.assertFalse(is_caption("図書室に行きます")) # "図" の直後に数字が続かない

    def test_split_by_sections(self):
        """セクション分割のテスト"""
        text = (
            "はじめに\n"
            "これは序文です。\n"
            "第1章 基礎知識\n"
            "ここは第1章です。\n"
            "1.1 節のタイトル\n"
            "節の内容です。"
        )
        chunks = split_by_sections(text)
        
        # split_by_sections はヘッダーと本文を結合して返す仕様
        self.assertTrue(len(chunks) >= 3)
        self.assertIn("はじめに", chunks[0])
        self.assertIn("第1章", chunks[1])
        # 正規表現のマッチ範囲により、ヘッダー部分がどう抽出されるか確認
        # 第1章は `第[0-9]+章` にマッチするため、タイトル "基礎知識" は本文側に回る可能性があるが、
        # 最終的に結合されるためチャンク内には含まれるはず。
        self.assertIn("基礎知識", chunks[1])

    def test_split_into_sentences(self):
        """文分割のテスト"""
        # ピリオド+スペース、または連続する改行で分割されるか
        text = "This is sentence 1. This is sentence 2.\n\nNew paragraph."
        sentences = split_into_sentences(text)
        
        self.assertIn("This is sentence 1.", sentences)
        self.assertIn("This is sentence 2.", sentences)
        self.assertIn("New paragraph.", sentences)

    def test_chunk_text_flow(self):
        """統合チャンク化処理のテスト"""
        text = (
            "第1章 テスト\n"
            "This is a sentence. " * 10 + "\n"
            "$$ math_formula $$"
        )
        chunks = chunk_text(text)
        self.assertTrue(len(chunks) > 0)
        # セクションヘッダーが含まれていること
        self.assertIn("第1章", chunks[0])

    def test_chunk_text_copyright_filter(self):
        """著作権表記によるチャンク削除のテスト"""
        # 通常のコンテンツ
        text_normal = "Valid content."
        chunks_normal = chunk_text(text_normal)
        self.assertEqual(len(chunks_normal), 1)

        # 著作権表記のみのコンテンツ（削除されるべき）
        text_copy = "Copyright (c) 2023 by Author."
        chunks_copy = chunk_text(text_copy)
        self.assertEqual(len(chunks_copy), 0)

if __name__ == '__main__':
    unittest.main()