#!/usr/bin/env python3
"""Index logs or a JSONL source into FaissStore for RAG demos."""
import argparse
import json
import os
from typing import List

from src.rag.embed_store import FaissStore

# try to import batched embedder
try:
    from src.rag.embedding_backend import BatchedEmbedder
except Exception:
    BatchedEmbedder = None


def load_jsonl(path: str, limit: int = None) -> List[dict]:
    out = []
    with open(path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            line = line.strip()
            if not line:
                continue
            try:
                j = json.loads(line)
                out.append(j)
            except Exception:
                continue
    return out


def doc_from_feedback(j: dict) -> dict:
    text_parts = []
    if 'user_query' in j:
        text_parts.append(j.get('user_query'))
    if 'model_response' in j:
        text_parts.append(j.get('model_response'))
    if j.get('feedback_text'):
        text_parts.append(j.get('feedback_text'))
    text = '\n'.join([p for p in text_parts if p])
    return {
        'id': j.get('id') or None,
        'text': text,
        'meta': {
            'source': 'logs/feedback',
            'timestamp': j.get('timestamp'),
            'rating': j.get('rating'),
            'tags': j.get('tags')
        }
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', default='logs/feedback/feedback_history.jsonl')
    p.add_argument('--limit', type=int, default=500)
    p.add_argument('--index-path', default='corpus/rag_store.index')
    p.add_argument('--meta-path', default='corpus/rag_store_meta.json')
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

    # choose dim based on embedder if available
    dim = getattr(be, 'dim', 8) if be else 8

    store = FaissStore(index_path=args.index_path, meta_path=args.meta_path, dim=dim, batched_embedder=be)

    if not os.path.exists(args.source):
        print('Source not found:', args.source)
        raise SystemExit(1)

    items = load_jsonl(args.source, limit=args.limit)
    docs = [doc_from_feedback(j) for j in items]

    # ensure every doc has id
    for i, d in enumerate(docs):
        if not d.get('id'):
            d['id'] = f"fb_{i}"

    print(f'Indexing {len(docs)} docs to {args.index_path} (dim={dim})')
    ids = store.upsert(docs)
    print('Indexed ids:', len(ids))


if __name__ == '__main__':
    main()
