#!/usr/bin/env python3
"""Recreate Faiss index using BatchedEmbedder when available.

Usage:
  python scripts/reindex_with_batched_embedder.py --meta-path corpus/rag_store_meta.json --index-path corpus/rag_store.index --dry-run
"""
import argparse
import json
import os
import shutil
import sys

def load_meta(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def docs_from_meta(meta_list):
    docs = []
    for m in meta_list:
        text = m.get('text') or m.get('content') or m.get('result') or ''
        docs.append({'id': m.get('id'), 'text': text, 'meta': m.get('meta', {})})
    return docs


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--meta-path', default='corpus/rag_store_meta.json')
    p.add_argument('--index-path', default='corpus/rag_store.index')
    p.add_argument('--model', default='BAAI/bge-m3')
    p.add_argument('--temp-suffix', default='.new')
    p.add_argument('--backup-suffix', default='.bak')
    p.add_argument('--limit', type=int, default=None)
    p.add_argument('--force', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--batch-size', type=int, default=1024)
    args = p.parse_args()

    # try import batched embedder
    try:
        from src.rag.embedding_backend import BatchedEmbedder
    except Exception:
        BatchedEmbedder = None

    if BatchedEmbedder is None:
        print('BatchedEmbedder not available in codebase; aborting')
        sys.exit(0)

    try:
        be = BatchedEmbedder(model_name=args.model)
        if not getattr(be, 'available', False):
            print('BatchedEmbedder imported but not available on this system')
            sys.exit(0)
    except Exception as e:
        print('Failed to instantiate BatchedEmbedder:', e)
        sys.exit(1)

    # determine embedding dim by probing one sample if no attribute provided
    new_dim = getattr(be, 'dim', None) or getattr(be, 'embedding_dim', None)
    if not new_dim:
        try:
            import numpy as _np
            test_emb = be.embed(['test'])
            if isinstance(test_emb, _np.ndarray) and test_emb.ndim == 2:
                new_dim = int(test_emb.shape[1])
        except Exception:
            new_dim = None

    if not new_dim:
        print('Could not determine embedder dimension; aborting')
        sys.exit(1)

    print(f'BatchedEmbedder available: dim={new_dim}')

    # inspect existing index if any
    try:
        import faiss
        if os.path.exists(args.index_path):
            idx = faiss.read_index(args.index_path)
            try:
                base = idx.index
            except Exception:
                base = idx
            current_dim = getattr(base, 'd', None)
        else:
            current_dim = None
    except Exception:
        current_dim = None

    print('Current index dim:', current_dim)

    if current_dim is not None and current_dim >= int(new_dim) and not args.force:
        print('Existing index dimension is >= embedder dim; no reindex needed.')
        sys.exit(0)

    # load meta and prepare docs
    meta = load_meta(args.meta_path)
    if not meta:
        print('No meta found at', args.meta_path)
        # nothing to index
        sys.exit(0)

    docs = docs_from_meta(meta)
    if args.limit:
        docs = docs[:args.limit]

    print(f'Will reindex {len(docs)} documents to dim={new_dim}')

    if args.dry_run:
        print('Dry run enabled — aborting before writing index')
        sys.exit(0)

    # create temporary index and meta paths
    temp_index = args.index_path + args.temp_suffix
    temp_meta = args.meta_path + args.temp_suffix

    # build index using FaissStore
    try:
        from src.rag.embed_store import FaissStore
    except Exception as e:
        print('Failed to import FaissStore:', e)
        sys.exit(1)

    store = FaissStore(index_path=temp_index, meta_path=temp_meta, dim=int(new_dim), batched_embedder=be)

    # perform upsert in batches
    for i in range(0, len(docs), args.batch_size):
        batch = docs[i:i+args.batch_size]
        print(f'Indexing batch {i}..{i+len(batch)}')
        store.upsert(batch, batch_size=0)

    # final save occurred in FaissStore._save

    # backup old files and move new into place
    try:
        if os.path.exists(args.index_path):
            shutil.move(args.index_path, args.index_path + args.backup_suffix)
        if os.path.exists(args.meta_path):
            shutil.move(args.meta_path, args.meta_path + args.backup_suffix)
        shutil.move(temp_index, args.index_path)
        shutil.move(temp_meta, args.meta_path)
        print('Reindex complete; backups saved with suffix', args.backup_suffix)
    except Exception as e:
        print('Failed to replace index atomically:', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
