"""Batched embedding backend.

Provides `BatchedEmbedder` which attempts to load a HuggingFace transformer
model/tokenizer for batched inference. If transformers or the model are not
available, `available` is False and callers should fall back to other embed
functions.

This module is optional; it does not force model downloads on import if the
environment lacks `transformers` or `torch`.
"""
from typing import List, Optional
import numpy as np


class BatchedEmbedder:
    def __init__(self, model_name: str = "BAAI/bge-m3", device: Optional[str] = None, batch_size: int = 32):
        self.model_name = model_name
        self.batch_size = batch_size
        self.available = False
        self.device = device

        try:
            import torch
            from transformers import AutoTokenizer, AutoModel
        except Exception:
            # transformers or torch not available
            self.available = False
            return

        if self.device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"

        try:
            # load model and tokenizer lazily
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)
            self.model = AutoModel.from_pretrained(self.model_name, trust_remote_code=True).to(self.device)
            self.model.eval()
            self.torch = torch
            self.available = True
        except Exception:
            self.available = False

    def embed(self, texts: List[str]) -> np.ndarray:
        """Embed a list of texts and return (N, D) float32 array.

        Raises RuntimeError if embedder is not available.
        """
        if not self.available:
            raise RuntimeError("BatchedEmbedder not available in this environment")

        toks = self.tokenizer
        model = self.model
        torch = self.torch

        all_embs = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i+self.batch_size]
            inputs = toks(batch, return_tensors='pt', padding=True, truncation=True, max_length=2048).to(self.device)
            with torch.no_grad():
                outputs = model(**inputs)
                # try CLS token then mean pooling fallback
                if hasattr(outputs, 'last_hidden_state'):
                    emb = outputs.last_hidden_state[:, 0, :]
                else:
                    # fallback: mean pool hidden states if CLS not present
                    last = outputs[0]
                    emb = last.mean(dim=1)
                emb = torch.nn.functional.normalize(emb, p=2, dim=1)
                all_embs.append(emb.cpu().numpy())

        return np.vstack(all_embs).astype('float32')
