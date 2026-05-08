#!/usr/bin/env python3
"""
トークン化パイプライン

テキストをトークン列に変換し、パディング・バッチ処理を行う
"""

import torch
import logging
from typing import List, Tuple, Optional, Union
import re

logger = logging.getLogger(__name__)


class SimpleTokenizer:
    """
    シンプルなトークナイザー実装
    （実際の運用ではBPEやSentencePieceを使用）
    """
    
    def __init__(self, vocab_size: int = 50257):
        """
        初期化
        
        Args:
            vocab_size: ボキャブラリサイズ
        """
        self.vocab_size = vocab_size
        self.vocab = self._build_vocab()
        logger.info(f"Initialized SimpleTokenizer (vocab_size={vocab_size})")
    
    def _build_vocab(self) -> dict:
        """基本的なボキャブラリを構築"""
        vocab = {}
        
        # 特殊トークン
        special_tokens = ['[PAD]', '[UNK]', '[CLS]', '[SEP]', '[MASK]']
        for i, token in enumerate(special_tokens):
            vocab[token] = i
        
        # 一般的な単語
        common_words = [
            'the', 'a', 'an', 'and', 'or', 'is', 'are', 'was', 'were',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'can', 'to', 'of',
            'in', 'on', 'at', 'by', 'for', 'with', 'from', 'up', 'about'
        ]
        
        idx = len(special_tokens)
        for word in common_words:
            if idx < self.vocab_size:
                vocab[word] = idx
                idx += 1
        
        return vocab
    
    def encode(self, text: str) -> List[int]:
        """
        テキストをトークンに変換
        
        Args:
            text: 入力テキスト
            
        Returns:
            トークンIDのリスト
        """
        # テキストを小文字に変換
        text = text.lower()
        
        # 単語に分割（シンプルな正規表現ベース）
        words = re.findall(r'\b\w+\b', text)
        
        tokens = []
        for word in words:
            if word in self.vocab:
                tokens.append(self.vocab[word])
            else:
                # 未知語は [UNK] トークン (ID=1)
                tokens.append(1)
        
        return tokens
    
    def decode(self, token_ids: Union[List[int], torch.Tensor]) -> str:
        """
        トークンをテキストに変換
        
        Args:
            token_ids: トークンIDのリスト
            
        Returns:
            デコードされたテキスト
        """
        if isinstance(token_ids, torch.Tensor):
            token_ids = token_ids.tolist()
        
        # トークン ID から単語への逆写像を作成
        reverse_vocab = {v: k for k, v in self.vocab.items()}
        
        words = []
        for token_id in token_ids:
            if token_id in reverse_vocab:
                word = reverse_vocab[token_id]
                if not word.startswith('['):
                    words.append(word)
        
        return ' '.join(words)


class TokenizationPipeline:
    """
    テキスト処理のパイプライン
    """
    
    def __init__(self, vocab_size: int = 50257, max_length: int = 512,
                 tokenizer: Optional[SimpleTokenizer] = None):
        """
        初期化
        
        Args:
            vocab_size: ボキャブラリサイズ
            max_length: 最大シーケンス長
            tokenizer: カスタムトークナイザー
        """
        self.vocab_size = vocab_size
        self.max_length = max_length
        self.tokenizer = tokenizer or SimpleTokenizer(vocab_size)
        
        logger.info(f"Initialized TokenizationPipeline "
                   f"(max_length={max_length})")
    
    def preprocess(self, text: str) -> str:
        """
        テキスト前処理
        
        Args:
            text: 入力テキスト
            
        Returns:
            前処理済みテキスト
        """
        # 余分な空白を削除
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 特殊文字の正規化
        text = text.replace('　', ' ')  # 全角スペースを半角に
        
        return text
    
    def encode(self, text: str, padding: bool = True, 
               pad_to_length: Optional[int] = None) -> torch.Tensor:
        """
        テキストをエンコード
        
        Args:
            text: 入力テキスト
            padding: パディングするか
            pad_to_length: パディング対象の長さ
            
        Returns:
            トークンテンソル
        """
        # 前処理
        text = self.preprocess(text)
        
        # トークン化
        tokens = self.tokenizer.encode(text)
        
        # 長さを制限
        if len(tokens) > self.max_length:
            tokens = tokens[:self.max_length]
        
        # パディング
        if padding:
            pad_length = pad_to_length or self.max_length
            if len(tokens) < pad_length:
                tokens = tokens + [0] * (pad_length - len(tokens))  # PAD token = 0
        
        return torch.tensor(tokens, dtype=torch.long)
    
    def decode(self, token_ids: Union[List[int], torch.Tensor]) -> str:
        """
        トークンをデコード
        
        Args:
            token_ids: トークンIDのリスト
            
        Returns:
            デコードされたテキスト
        """
        return self.tokenizer.decode(token_ids)
    
    def batch_encode(self, texts: List[str], 
                    return_tensors: bool = True) -> Union[List[torch.Tensor], torch.Tensor]:
        """
        複数テキストをバッチエンコード
        
        Args:
            texts: テキストのリスト
            return_tensors: テンソルを返すか
            
        Returns:
            バッチエンコード結果
        """
        encoded_list = []
        max_len = 0
        
        # 最初のパスで最大長を取得
        for text in texts:
            text = self.preprocess(text)
            tokens = self.tokenizer.encode(text)
            max_len = max(max_len, len(tokens))
            encoded_list.append(tokens)
        
        # パディング
        padded_list = []
        for tokens in encoded_list:
            padded = tokens + [0] * (max_len - len(tokens))
            padded_list.append(padded)
        
        if return_tensors:
            # テンソルに変換
            return torch.tensor(padded_list, dtype=torch.long)
        else:
            return padded_list
    
    def get_attention_mask(self, token_ids: torch.Tensor) -> torch.Tensor:
        """
        アテンションマスクを生成
        
        Args:
            token_ids: トークンテンソル
            
        Returns:
            アテンションマスク
        """
        # PAD トークン (0) は mask = 0, その他は mask = 1
        if len(token_ids.shape) == 1:
            attention_mask = (token_ids != 0).int()
        else:
            attention_mask = (token_ids != 0).int()
        
        return attention_mask
    
    def get_token_length(self, token_ids: torch.Tensor) -> int:
        """
        パディングを除いた実際のトークン数を取得
        
        Args:
            token_ids: トークンテンソル
            
        Returns:
            実際のトークン数
        """
        if len(token_ids.shape) == 1:
            return (token_ids != 0).sum().item()
        else:
            # バッチの場合は各要素の長さ
            return (token_ids != 0).sum(dim=1).tolist()


def demo():
    """デモンストレーション"""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*80)
    print("トークン化パイプライン デモンストレーション")
    print("="*80)
    
    # パイプラインを初期化
    pipeline = TokenizationPipeline(max_length=128)
    
    # テスト1: 単一テキストのエンコード
    print("\n[1] 単一テキストのエンコード:")
    text = "What is the capital of France?"
    encoded = pipeline.encode(text, padding=True)
    print(f"  入力: {text}")
    print(f"  トークン数: {len(encoded)}")
    print(f"  トークン: {encoded[:20].tolist()}...")
    
    # デコード
    decoded = pipeline.decode(encoded)
    print(f"  デコード: {decoded}")
    
    # テスト2: バッチエンコード
    print("\n[2] バッチエンコード:")
    texts = [
        "Hello, how are you?",
        "What is machine learning?",
        "Python is a programming language."
    ]
    
    batch_encoded = pipeline.batch_encode(texts)
    print(f"  入力テキスト数: {len(texts)}")
    print(f"  バッチ形状: {batch_encoded.shape}")
    print(f"  最初のシーケンス: {batch_encoded[0, :20].tolist()}...")
    
    # テスト3: アテンションマスク
    print("\n[3] アテンションマスク:")
    attention_mask = pipeline.get_attention_mask(batch_encoded)
    print(f"  マスク形状: {attention_mask.shape}")
    print(f"  最初のマスク: {attention_mask[0].tolist()}")
    
    # テスト4: トークン長取得
    print("\n[4] 実際のトークン長:")
    lengths = pipeline.get_token_length(batch_encoded)
    print(f"  各シーケンスの長さ: {lengths}")
    
    print("\n✅ デモンストレーション完了")


if __name__ == "__main__":
    demo()
