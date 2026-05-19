#!/usr/bin/env python3
"""Small example: build a Faiss index from in-memory docs and run a query.

Usage:
  python3 scripts/rag_faiss_example.py

Dependencies:
  pip install sentence-transformers faiss-cpu numpy
"""
import sys
try:
    import faiss
except Exception:
    faiss = None
import numpy as np
from sentence_transformers import SentenceTransformer

DOCS = [
    "Python の基礎: 変数、関数、ループ",
    "機械学習: 教師あり学習、評価指標",
    "RAG: 埋め込みを用いた検索と生成の組合せ",
]

def build_index(texts, model_name='all-MiniLM-L6-v2'):
    model = SentenceTransformer(model_name)
    embs = model.encode(texts, convert_to_numpy=True)
    # normalize for cosine using inner product
    norms = np.linalg.norm(embs, axis=1, keepdims=True)
    embs = embs / (norms + 1e-8)
    if faiss is None:
        return (embs, None)
    d = embs.shape[1]
    index = faiss.IndexFlatIP(d)
    index.add(embs.astype('float32'))
    return (embs, index)

def search(query, texts, embs, index, topk=3):
    model = SentenceTransformer('all-MiniLM-L6-v2')
    q = model.encode([query], convert_to_numpy=True)[0]
    q = q / (np.linalg.norm(q) + 1e-8)
    if index is None:
        sims = (embs @ q) / (np.linalg.norm(embs, axis=1) * np.linalg.norm(q) + 1e-8)
        idx = np.argsort(-sims)[:topk]
        return [(int(i), float(sims[i]), texts[i]) for i in idx]
    else:
        D, I = index.search(np.array([q], dtype='float32'), topk)
        res = []
        for score, i in zip(D[0], I[0]):
            res.append((int(i), float(score), texts[i]))
        return res

def main():
    texts = DOCS
    embs, index = build_index(texts)
    print('Index built. Faiss available:', faiss is not None)
    while True:
        q = input('\nQuery (empty to exit): ').strip()
        if not q:
            break
        results = search(q, texts, embs, index, topk=3)
        print('\nTop results:')
        for i, score, txt in results:
            print(f'- [{i}] {score:.4f}  {txt}')

if __name__ == '__main__':
    main()
