#!/usr/bin/env python3
"""
Build FAISS index from saved numpy embedding batches and metadata.
- Looks for `corpus/embeddings/*.npy` and `corpus/metadata.jsonl` (optional)
- Produces `corpus/faiss_from_emb.index` and `corpus/faiss_meta.sqlite`

注意: faiss が未インストールの場合は実行前に `pip install faiss-cpu` などを行ってください。
"""
from __future__ import annotations
import numpy as np
from pathlib import Path
import json
import sqlite3
import argparse

try:
    import faiss
except Exception:
    faiss = None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--emb-dir', default='corpus/embeddings')
    ap.add_argument('--meta', default='corpus/metadata.jsonl')
    ap.add_argument('--out-index', default='corpus/faiss_from_emb.index')
    ap.add_argument('--out-meta', default='corpus/faiss_from_emb.sqlite')
    args = ap.parse_args()

    emb_dir = Path(args.emb_dir)
    files = sorted(emb_dir.glob('*.npy'))
    if not files:
        print('No embeddings found in', emb_dir)
        return

    # load first to get dim
    first = np.load(files[0])
    dim = first.shape[1]
    total = 0

    if faiss is None:
        print('faiss not available; install faiss-cpu or faiss-gpu')
        return

    index = faiss.IndexFlatIP(dim)

    # metadata DB
    conn = sqlite3.connect(args.out_meta)
    cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS docs(id INTEGER PRIMARY KEY, doc_id TEXT, meta JSON)')
    conn.commit()

    cur_id = 0
    for f in files:
        arr = np.load(f)
        print('Adding', arr.shape[0], 'vectors from', f)
        # normalize for IP if needed
        if arr.dtype != np.float32:
            arr = arr.astype('float32')
        faiss.normalize_L2(arr)
        index.add(arr)
        # append dummy metadata rows if metadata file missing
        for i in range(arr.shape[0]):
            docid = f'{f.name}:{i}'
            cur.execute('INSERT INTO docs(doc_id, meta) VALUES(?, ?)', (docid, json.dumps({'source_file': str(f)})))
        total += arr.shape[0]
        conn.commit()

    print('total vectors added:', total)
    faiss.write_index(index, args.out_index)
    conn.close()
    print('wrote index ->', args.out_index, 'meta ->', args.out_meta)

if __name__ == '__main__':
    main()
