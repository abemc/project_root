#!/usr/bin/env python3
"""Query the FaissStore index created by rag_index.py"""
import argparse
import json
import numpy as np

from src.rag.embed_store import FaissStore
try:
    from src.rag.embedding_backend import BatchedEmbedder
except Exception:
    BatchedEmbedder = None


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--index-path', default='corpus/rag_store.index')
    p.add_argument('--meta-path', default='corpus/rag_store_meta.json')
    p.add_argument('--query', required=True)
    p.add_argument('--top-k', type=int, default=5)
    args = p.parse_args()

    if BatchedEmbedder is not None:
        try:
            be = BatchedEmbedder(model_name=None)
            if not getattr(be, 'available', False):
                be = None
        except Exception:
            be = None
    else:
        be = None

    dim = getattr(be, 'dim', 8) if be else 8
    store = FaissStore(index_path=args.index_path, meta_path=args.meta_path, dim=dim, batched_embedder=be)

    # embed query
    if be:
        qv = be.embed([args.query])[0]
    else:
        qv = store.embed_fn(args.query) if hasattr(store, 'embed_fn') else None
    if qv is None:
        print('Failed to compute embedding for query')
        return

    res = store.search(qv, top_k=args.top_k)
    print(json.dumps(res, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
