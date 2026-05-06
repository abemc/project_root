import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

import sentencepiece


class Reranker:
    def __init__(self, model_name="BAAI/bge-reranker-base"):
        """
        Rerankerを初期化します。

        Args:
            model_name (str): 使用するCross-Encoderモデルの名前。
        """
        print(f"Loading reranker model ({model_name})...")

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
        )
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            use_safetensors=True
        )
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self.device)
        self.score_threshold = 0.0 # GUIから動的に設定されるスコア閾値

    def rerank(self, query: str, contexts: list[dict], top_k: int = 5):
        if not contexts:
            return []

        pairs = [[query, c.get("text", "")] for c in contexts]

        inputs = self.tokenizer(
            pairs,
            padding=True,
            truncation=True,
            return_tensors="pt"
        ).to(self.device)

        with torch.no_grad():
            scores = self.model(**inputs).logits.squeeze(dim=1)
            # スコアを sigmoid で 0-1 の範囲に変換し、閾値との比較を直感的にします
            scores = torch.sigmoid(scores)

        # 各ドキュメントにrerankスコアを追加
        for ctx, score in zip(contexts, scores):
            ctx['rerank_score'] = float(score)

        # スコア閾値でフィルタリング
        filtered_contexts = [ctx for ctx in contexts if ctx['rerank_score'] >= self.score_threshold]

        # rerankスコアで降順にソート
        filtered_contexts.sort(key=lambda x: x['rerank_score'], reverse=True)

        # 上位 top_k を返す
        return filtered_contexts[:top_k]