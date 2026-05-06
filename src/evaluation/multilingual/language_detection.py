"""
言語検出・判定モジュール
"""

import re
from typing import Tuple


class LanguageDetector:
    """
    テキストから言語を自動判定するクラス
    
    対応言語:
    - EN (英語)
    - JA (日本語)
    """
    
    def __init__(self):
        """言語検出エンジンの初期化"""
        # 日本語文字の正規表現パターン
        self.japanese_pattern = re.compile(
            r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]+'
        )
        
        # 英語単語パターン
        self.english_pattern = re.compile(r'[a-zA-Z]+')
        
    def detect(self, text: str) -> str:
        """
        テキストから言語を検出
        
        Args:
            text (str): 入力テキスト
            
        Returns:
            str: 言語コード ('EN' または 'JA')
        """
        if not text or len(text) == 0:
            return 'EN'  # デフォルト
            
        # 日本語文字の出現数をカウント
        japanese_matches = self.japanese_pattern.findall(text)
        english_matches = self.english_pattern.findall(text)
        
        japanese_ratio = len(japanese_matches) / (len(text) / 10) if text else 0
        english_ratio = len(english_matches) / (len(text) / 10) if text else 0
        
        # 日本語比率が高い場合は日本語と判定
        if japanese_ratio > english_ratio * 1.5:
            return 'JA'
        
        return 'EN'
    
    def get_language_name(self, lang_code: str) -> str:
        """
        言語コードから言語名を取得
        
        Args:
            lang_code (str): 言語コード ('EN' または 'JA')
            
        Returns:
            str: 言語名
        """
        language_map = {
            'EN': 'English',
            'JA': '日本語',
        }
        return language_map.get(lang_code, 'Unknown')
    
    def detect_with_confidence(self, text: str) -> Tuple[str, float]:
        """
        言語を検出し、確信度を返す
        
        Args:
            text (str): 入力テキスト
            
        Returns:
            Tuple[str, float]: (言語コード, 確信度 0.0-1.0)
        """
        if not text or len(text) == 0:
            return 'EN', 0.5
        
        japanese_matches = self.japanese_pattern.findall(text)
        english_matches = self.english_pattern.findall(text)
        
        japanese_count = len(japanese_matches)
        english_count = len(english_matches)
        
        total_matches = japanese_count + english_count
        
        if total_matches == 0:
            return 'EN', 0.5
        
        japanese_ratio = japanese_count / total_matches
        
        if japanese_ratio > 0.3:
            confidence = japanese_ratio
            return 'JA', confidence
        else:
            confidence = english_count / total_matches
            return 'EN', confidence
