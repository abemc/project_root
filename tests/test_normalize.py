import unittest
import sys
import os

# プロジェクトルートをパスに追加して src モジュールをインポートできるようにする
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.corpus.normalize import (
    normalize_text,
    protect_formulas, restore_formulas,
    protect_code_blocks, restore_code_blocks,
    protect_captions, restore_captions,
    protect_api_names, restore_api_names,
    clean_ocr_noise
)

class TestNormalize(unittest.TestCase):

    def test_protect_formulas(self):
        """数式の保護と復元のテスト"""
        raw = r"Here is inline $E=mc^2$ and display $$ \sum_{i=0}^n i $$ formula."
        
        # 保護
        protected, formulas = protect_formulas(raw)
        # normalize.pyの実装順序により、display ($$) が先に処理されるため、inlineはindex 1になる
        self.assertIn("§INLINE_FORMULA§1", protected)
        self.assertIn("§DISPLAY_FORMULA§0", protected)
        self.assertEqual(len(formulas), 2)
        self.assertEqual(formulas[0], r"$$ \sum_{i=0}^n i $$") # display $$ matches first due to logic order or position? 
        # normalize.pyの実装順序により、display ($$) が先に処理される
        
        # 復元
        restored = restore_formulas(protected, formulas)
        self.assertEqual(restored, raw)

    def test_protect_formulas_latex_envs(self):
        """LaTeX環境形式の数式保護テスト"""
        raw = r"""
        \begin{equation}
            a = b
        \end{equation}
        Text
        \begin{align}
            c &= d
        \end{align}
        """
        protected, formulas = protect_formulas(raw)
        self.assertIn("§DISPLAY_FORMULA§0", protected)
        self.assertIn("§DISPLAY_FORMULA§1", protected)
        self.assertEqual(len(formulas), 2)
        
        restored = restore_formulas(protected, formulas)
        self.assertEqual(restored, raw)

    def test_protect_code_blocks(self):
        """コードブロックの保護と復元のテスト"""
        # Markdown Fenced Code Block
        raw_fenced = "Code:\n```python\nprint('hello')\n```\nEnd."
        protected, blocks = protect_code_blocks(raw_fenced)
        self.assertIn("§CODE_BLOCK§0", protected)
        self.assertEqual(blocks[0], "```python\nprint('hello')\n```")
        self.assertEqual(restore_code_blocks(protected, blocks), raw_fenced)

        # Indented Code Block
        raw_indented = "Text.\n\n    def foo():\n        return 1\n\nNext line."
        protected, blocks = protect_code_blocks(raw_indented)
        self.assertIn("§CODE_BLOCK§", protected)
        # インデントブロックが正しくキャプチャされているか
        self.assertIn("def foo():", blocks[0])
        self.assertEqual(restore_code_blocks(protected, blocks), raw_indented)

    def test_protect_captions(self):
        """図表キャプションの保護と復元のテスト"""
        raw = "See the result below.\nFigure 1: This is a chart.\nNext paragraph."
        protected, captions = protect_captions(raw)
        
        # "Figure 1: ..." 行がトークンに置き換わっているはず
        self.assertIn("§CAPTION§0", protected)
        self.assertNotIn("Figure 1:", protected)
        self.assertEqual(captions[0], "Figure 1: This is a chart.")
        
        restored = restore_captions(protected, captions)
        self.assertEqual(restored, raw)

    def test_protect_api_names(self):
        """API名の保護と復元のテスト"""
        raw = "Use torch.nn.Linear and numpy.array here."
        protected, apis = protect_api_names(raw)
        
        self.assertIn("§API§0", protected)
        self.assertIn("§API§1", protected)
        self.assertNotIn("torch.nn.Linear", protected)
        
        restored = restore_api_names(protected, apis)
        self.assertEqual(restored, raw)

    def test_clean_ocr_noise(self):
        """OCRノイズ除去のテスト"""
        raw = "This is a ﬁne day with 1 − 2 errors… and “quotes”."
        expected = 'This is a fine day with 1 - 2 errors... and "quotes".'
        cleaned = clean_ocr_noise(raw)
        self.assertEqual(cleaned, expected)

        # 連続する記号ノイズの除去
        noise_text = "Table of Contents ......___ 1"
        cleaned_noise = clean_ocr_noise(noise_text)
        self.assertEqual(cleaned_noise, "Table of Contents   1")

    def test_normalize_text_full_flow(self):
        """統合正規化処理のテスト"""
        # 入力:
        # 1. 日本語間のスペースあり
        # 2. 数式 ($x$)
        # 3. OCRノイズ (ﬁ)
        # 4. 余分な空白と改行
        raw = (
            "これ  は    テスト   です。\n"
            "値 は $x = 10$ で ある。\n"
            "Definition 1.2: ﬁnal result."
        )
        
        # 期待値:
        # 1. スペース削除 -> これはテストです。
        # 2. 数式は維持
        # 3. ﬁ -> fi
        # 4. 改行は\nに統一、連続空白は1つに、前後はstrip
        
        # Definition 1.2: ... は protect_captions の正規表現にはマッチしない可能性がある
        # (現在の正規表現は Figure, Table, Listing, 図, 表, リスト)
        # したがって、Definitionは通常のテキストとして処理される前提でテストを書くか、
        # API名として誤爆しないか確認する。 "Definition" はAPIパターンにはマッチしない。
        
        expected = "これはテストです。\n値は $x = 10$ である。\nDefinition 1.2: final result."
        
        result = normalize_text(raw)
        self.assertEqual(result, expected)

    def test_normalize_japanese_spacing(self):
        """日本語文字間のスペース削除テスト"""
        raw = "データ の 学習 データ"
        expected = "データの学習データ"
        # normalize_text を通すと API保護などが走るが、結果的にスペースが消えるか確認
        result = normalize_text(raw)
        self.assertEqual(result, expected)

if __name__ == '__main__':
    unittest.main()