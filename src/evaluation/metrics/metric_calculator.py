"""
評価メトリクス計算モジュール

このモジュールは、言語モデルの評価に使用される各種メトリクスを提供します：
- 正解率 (Accuracy)
- F1スコア
- BLEU スコア（テキスト生成）
- ROUGE スコア（要約）
"""

import numpy as np
from typing import List, Dict, Any, Union
from collections import Counter
import re


class AccuracyMetric:
    """正解率を計算するメトリクス"""
    
    @staticmethod
    def compute(predictions: List[str], references: List[str]) -> float:
        """
        正解率を計算
        
        Args:
            predictions: モデルの予測リスト
            references: 参照回答リスト
            
        Returns:
            正解率 (0.0-1.0)
        """
        if len(predictions) != len(references):
            raise ValueError("予測と参照の長さが一致しません")
        
        correct = sum(
            1 for pred, ref in zip(predictions, references)
            if str(pred).strip() == str(ref).strip()
        )
        
        return correct / len(predictions) if predictions else 0.0


class F1ScoreMetric:
    """F1スコアを計算するメトリクス"""
    
    @staticmethod
    def compute(predictions: List[str], references: List[str], 
                average: str = "macro") -> float:
        """
        F1スコアを計算
        
        Args:
            predictions: モデルの予測リスト
            references: 参照回答リスト
            average: 'macro', 'micro', 'weighted'
            
        Returns:
            F1スコア (0.0-1.0)
        """
        if len(predictions) != len(references):
            raise ValueError("予測と参照の長さが一致しません")
        
        if average == "macro":
            # 各サンプルでのF1の平均
            f1_scores = []
            for pred, ref in zip(predictions, references):
                pred_set = set(str(pred).lower().split())
                ref_set = set(str(ref).lower().split())
                
                if len(ref_set) == 0:
                    f1 = 1.0 if len(pred_set) == 0 else 0.0
                else:
                    intersection = len(pred_set & ref_set)
                    if len(pred_set) == 0:
                        precision = 0.0
                    else:
                        precision = intersection / len(pred_set)
                    
                    recall = intersection / len(ref_set)
                    
                    if precision + recall == 0:
                        f1 = 0.0
                    else:
                        f1 = 2 * (precision * recall) / (precision + recall)
                
                f1_scores.append(f1)
            
            return np.mean(f1_scores)
        
        elif average == "micro":
            # 全体でのprecision/recallを計算
            total_intersection = 0
            total_pred = 0
            total_ref = 0
            
            for pred, ref in zip(predictions, references):
                pred_set = set(str(pred).lower().split())
                ref_set = set(str(ref).lower().split())
                
                total_intersection += len(pred_set & ref_set)
                total_pred += len(pred_set)
                total_ref += len(ref_set)
            
            if total_pred == 0:
                precision = 0.0
            else:
                precision = total_intersection / total_pred
            
            if total_ref == 0:
                recall = 0.0
            else:
                recall = total_intersection / total_ref
            
            if precision + recall == 0:
                return 0.0
            else:
                return 2 * (precision * recall) / (precision + recall)
        
        else:
            raise ValueError(f"Unknown average type: {average}")


class BLEUScoreMetric:
    """BLEU スコア（翻訳・生成評価）"""
    
    @staticmethod
    def _get_ngrams(segment: str, max_order: int) -> Dict[tuple, int]:
        """n-gramを抽出"""
        ngram_counts = {}
        for order in range(1, max_order + 1):
            for i in range(0, len(segment) - order + 1):
                ngram = tuple(segment[i:i + order])
                ngram_counts[ngram] = ngram_counts.get(ngram, 0) + 1
        return ngram_counts
    
    @staticmethod
    def compute(predictions: List[str], references: List[List[str]], 
                max_order: int = 4, smooth: bool = False) -> float:
        """
        BLEU スコアを計算
        
        Args:
            predictions: モデルの予測リスト
            references: 参照回答のリスト（各予測に対して複数の参照可能）
            max_order: 最大n-gram次数
            smooth: スムージングを適用するか
            
        Returns:
            BLEUスコア (0.0-1.0)
        """
        matches_by_order = [0] * max_order
        possible_matches_by_order = [0] * max_order
        reference_length = 0
        translation_length = 0
        
        for (prediction, reference_list) in zip(predictions, references):
            # 文字列をトークン化
            pred_tokens = prediction.lower().split()
            translation_length += len(pred_tokens)
            
            ref_lens = [len(r.lower().split()) for r in reference_list]
            reference_length += min(ref_lens, key=lambda x: (abs(x - len(pred_tokens)), x))
            
            merged_ref_ngram_counts = {}
            for reference in reference_list:
                ref_tokens = reference.lower().split()
                ref_ngrams = BLEUScoreMetric._get_ngrams(ref_tokens, max_order)
                for ngram in ref_ngrams:
                    merged_ref_ngram_counts[ngram] = max(
                        merged_ref_ngram_counts.get(ngram, 0),
                        ref_ngrams[ngram]
                    )
            
            pred_ngrams = BLEUScoreMetric._get_ngrams(pred_tokens, max_order)
            for ngram in pred_ngrams:
                matches = min(pred_ngrams.get(ngram, 0),
                            merged_ref_ngram_counts.get(ngram, 0))
                matches_by_order[len(ngram) - 1] += matches
                possible_matches_by_order[len(ngram) - 1] += pred_ngrams.get(ngram, 0)
        
        precisions = [0] * max_order
        for i in range(0, max_order):
            if smooth:
                precisions[i] = ((matches_by_order[i] + 1.) /
                               (possible_matches_by_order[i] + 1.))
            else:
                if possible_matches_by_order[i] > 0:
                    precisions[i] = (float(matches_by_order[i]) /
                                   possible_matches_by_order[i])
                else:
                    precisions[i] = 0.0
        
        if min(precisions) > 0:
            p_log_sum = sum((1. / max_order) * np.log(p) for p in precisions)
            geo_mean = np.exp(p_log_sum)
        else:
            geo_mean = 0
        
        ratio = float(translation_length) / reference_length if reference_length > 0 else 0
        
        if ratio > 1.0:
            bp = 1.0
        elif ratio > 0:
            bp = np.exp(1 - 1. / ratio)
        else:
            bp = 0.0
        
        bleu = geo_mean * bp
        return bleu


class ROUGEScoreMetric:
    """ROUGE スコア（要約評価）"""
    
    @staticmethod
    def _get_rouge_l(prediction: str, reference: str) -> float:
        """ROUGE-L を計算（最長共通部分列）"""
        pred_tokens = prediction.lower().split()
        ref_tokens = reference.lower().split()
        
        # LCS長を計算
        m, n = len(pred_tokens), len(ref_tokens)
        lcs_table = [[0] * (n + 1) for _ in range(m + 1)]
        
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if pred_tokens[i - 1] == ref_tokens[j - 1]:
                    lcs_table[i][j] = lcs_table[i - 1][j - 1] + 1
                else:
                    lcs_table[i][j] = max(lcs_table[i - 1][j], lcs_table[i][j - 1])
        
        lcs_len = lcs_table[m][n]
        
        if m == 0 or n == 0:
            return 1.0 if m == n else 0.0
        
        recall = lcs_len / n
        precision = lcs_len / m
        
        if recall + precision == 0:
            return 0.0
        
        rouge_l = 2 * (recall * precision) / (recall + precision)
        return rouge_l
    
    @staticmethod
    def compute(predictions: List[str], references: List[str]) -> Dict[str, float]:
        """
        ROUGE スコアを計算
        
        Args:
            predictions: モデルの予測リスト
            references: 参照回答リスト
            
        Returns:
            Rouge-L スコア
        """
        if len(predictions) != len(references):
            raise ValueError("予測と参照の長さが一致しません")
        
        rouge_l_scores = []
        for pred, ref in zip(predictions, references):
            rouge_l = ROUGEScoreMetric._get_rouge_l(pred, ref)
            rouge_l_scores.append(rouge_l)
        
        return {
            "rouge_l": np.mean(rouge_l_scores),
            "rouge_l_std": np.std(rouge_l_scores)
        }


class ExactMatchMetric:
    """完全一致率"""
    
    @staticmethod
    def compute(predictions: List[str], references: List[str]) -> float:
        """
        完全一致率を計算
        
        Args:
            predictions: モデルの予測リスト
            references: 参照回答リスト
            
        Returns:
            完全一致率 (0.0-1.0)
        """
        if len(predictions) != len(references):
            raise ValueError("予測と参照の長さが一致しません")
        
        exact_matches = 0
        for pred, ref in zip(predictions, references):
            # 複数の参照がある場合は、いずれかと一致すればカウント
            if isinstance(ref, list):
                if any(str(pred).strip() == str(r).strip() for r in ref):
                    exact_matches += 1
            else:
                if str(pred).strip() == str(ref).strip():
                    exact_matches += 1
        
        return exact_matches / len(predictions) if predictions else 0.0


class MetricCalculator:
    """複合メトリクス計算エンジン"""
    
    def __init__(self):
        self.accuracy = AccuracyMetric()
        self.f1 = F1ScoreMetric()
        self.bleu = BLEUScoreMetric()
        self.rouge = ROUGEScoreMetric()
        self.exact_match = ExactMatchMetric()
    
    def compute_all_metrics(self, 
                          predictions: List[str], 
                          references: Union[List[str], List[List[str]]],
                          task_type: str = "classification") -> Dict[str, float]:
        """
        複数のメトリクスを一括計算
        
        Args:
            predictions: モデルの予測
            references: 参照回答
            task_type: タスク種別 ('classification', 'generation', 'summarization')
            
        Returns:
            メトリクス辞書
        """
        results = {}
        
        # 参照データを正規化
        if references and isinstance(references[0], list):
            flat_references = [r[0] if r else "" for r in references]
        else:
            flat_references = references
        
        # 常に計算
        results["accuracy"] = self.accuracy.compute(predictions, flat_references)
        results["exact_match"] = self.exact_match.compute(predictions, references)
        results["f1"] = self.f1.compute(predictions, flat_references)
        
        if task_type in ["generation", "summarization"]:
            # 生成タスク
            # BLEU（参照が複数の場合用）
            if references and isinstance(references[0], list):
                results["bleu"] = self.bleu.compute(predictions, references)
            else:
                results["bleu"] = self.bleu.compute(predictions, [[r] for r in flat_references])
            
            # ROUGE（要約タスク）
            if task_type == "summarization":
                rouge_scores = self.rouge.compute(predictions, flat_references)
                results.update(rouge_scores)
        
        return results
