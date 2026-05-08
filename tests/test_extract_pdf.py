import unittest
from unittest.mock import MagicMock, patch, mock_open
import sys
import os

# プロジェクトルートをパスに追加して src モジュールをインポートできるようにする
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.corpus.extract_pdf import (
    load_translator,
    translate_en_to_ja,
    extract_pdf
)

class TestExtractPdf(unittest.TestCase):

    @patch('src.corpus.extract_pdf.AutoTokenizer')
    @patch('src.corpus.extract_pdf.AutoModelForSeq2SeqLM')
    def test_load_translator(self, mock_model_cls, mock_tokenizer_cls):
        """翻訳モデルのロード処理のテスト"""
        # モックの設定
        mock_tokenizer = MagicMock()
        mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer
        
        mock_model = MagicMock()
        # .cuda() の連鎖呼び出しに対応（.cuda() が self を返すと仮定）
        mock_model.cuda.return_value = mock_model 
        mock_model_cls.from_pretrained.return_value = mock_model

        # 実行
        tokenizer, model = load_translator()

        # 検証
        mock_tokenizer_cls.from_pretrained.assert_called_once()
        mock_model_cls.from_pretrained.assert_called_once()
        mock_model.cuda.assert_called_once()
        self.assertEqual(tokenizer, mock_tokenizer)
        self.assertEqual(model, mock_model)

    def test_translate_en_to_ja_empty(self):
        """空文字の翻訳スキップテスト"""
        tokenizer = MagicMock()
        model = MagicMock()
        result = translate_en_to_ja(tokenizer, model, "   ")
        self.assertEqual(result, "")
        model.generate.assert_not_called()

    def test_translate_en_to_ja_valid(self):
        """正常な翻訳処理のテスト"""
        tokenizer = MagicMock()
        model = MagicMock()
        text = "Hello world"
        
        # tokenizer の挙動モック
        inputs_mock = MagicMock()
        inputs_mock.to.return_value = inputs_mock
        tokenizer.return_value = inputs_mock
        tokenizer.lang_code_to_id = {"jpn_Jpan": 12345}
        
        # model.generate の挙動モック
        outputs_mock = [MagicMock()]
        model.generate.return_value = outputs_mock
        
        # tokenizer.decode の挙動モック
        tokenizer.decode.return_value = "こんにちは世界"
        
        # 実行
        result = translate_en_to_ja(tokenizer, model, text)
        
        # 検証
        tokenizer.assert_called_once()
        model.generate.assert_called_once()
        # 引数 forced_bos_token_id の確認
        _, kwargs = model.generate.call_args
        self.assertEqual(kwargs['forced_bos_token_id'], 12345)
        self.assertEqual(result, "こんにちは世界")

    @patch('src.corpus.extract_pdf.fitz.open')
    @patch('src.corpus.extract_pdf.pytesseract.image_to_string')
    @patch('src.corpus.extract_pdf.Image.open')
    @patch('src.corpus.extract_pdf.load_translator')
    @patch('src.corpus.extract_pdf.translate_en_to_ja')
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open) 
    def test_extract_pdf(self, mock_file_open, mock_makedirs, 
                         mock_translate, mock_load_translator, 
                         mock_img_open, mock_ocr, mock_fitz_open):
        """PDF抽出のメインフローテスト"""
        
        # PDFドキュメントのモック（1ページ）
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_doc.__len__.return_value = 1
        # enumerate(doc, 1) で反復されるため
        mock_doc.__iter__.return_value = iter([mock_page])
        mock_fitz_open.return_value = mock_doc
        
        # ページ画像化のモック
        mock_pix = MagicMock()
        mock_page.get_pixmap.return_value = mock_pix
        
        # 画像オープンのモック (.convert("L") に対応)
        mock_img_instance = MagicMock()
        mock_img_open.return_value = mock_img_instance
        mock_img_instance.convert.return_value = mock_img_instance
        
        # 翻訳モデルロードのモック
        mock_tokenizer = MagicMock()
        mock_model = MagicMock()
        mock_load_translator.return_value = (mock_tokenizer, mock_model)
        
        # OCR結果のモック
        mock_ocr.return_value = "English Text"
        
        # 翻訳結果のモック
        mock_translate.return_value = "Japanese Text"
        
        # 実行
        pdf_path = "dummy.pdf"
        out_dir = "dummy_out"
        pages_text = extract_pdf(pdf_path, out_dir)
        
        # 検証
        mock_makedirs.assert_called_with(out_dir, exist_ok=True)
        mock_fitz_open.assert_called_with(pdf_path)
        mock_pix.save.assert_called()
        mock_translate.assert_called()
        mock_file_open.assert_called()
        self.assertEqual(pages_text, ["Japanese Text"])

if __name__ == '__main__':
    unittest.main()