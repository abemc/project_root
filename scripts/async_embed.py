#!/usr/bin/env python3
"""
非同期/バッチ埋め込みスクリプト（簡易実装）
- sentence-transformers を使い、GPU があれば CUDA を使用
- 入力: corpus/dataset.jsonl または corpus/normalized/*.txt
- 出力: numpy .npy ファイル（embeddings per-batch）または一つの memmapped file

使い方例:
  python scripts/async_embed.py --source corpus/dataset.jsonl --batch-size 128 --device auto --out-dir corpus/embeddings --dry-run
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from tqdm import tqdm
import numpy as np
import os

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None


def get_device(arg: str) -> str:
    if arg == 'auto':
        # prefer cuda if available
        try:
            import torch
            return 'cuda' if torch.cuda.is_available() else 'cpu'
        except Exception:
            return 'cpu'
    return arg


def load_texts_from_jsonl(path: Path, limit: int = 0):
    with path.open('r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            obj = json.loads(line)
            # assume text field exists
            txt = obj.get('text') or obj.get('content') or obj.get('body')
            if txt:
                yield txt


def embed_texts(model_name: str, texts, batch_size: int, device: str):
    if SentenceTransformer is None:
        raise RuntimeError('sentence_transformers not installed')
    model = SentenceTransformer(model_name_or_path=model_name, device=device)
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        embs = model.encode(batch, show_progress_bar=False, convert_to_numpy=True, batch_size=batch_size)
        yield i, embs


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True)
    p.add_argument('--model', default='intfloat/multilingual-e5-small')
    p.add_argument('--batch-size', type=int, default=64)
    p.add_argument('--device', default='auto')
    p.add_argument('--limit', type=int, default=0)
    p.add_argument('--out-dir', default='corpus/embeddings')
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()

    device = get_device(args.device)
    outd = Path(args.out_dir)
    outd.mkdir(parents=True, exist_ok=True)

    texts = []
    src = Path(args.source)
    if src.suffix == '.jsonl':
        texts = list(load_texts_from_jsonl(src, limit=args.limit))
    else:
        # assume dir of txt files
        pth = Path(args.source)
        for f in sorted(pth.glob('*.txt')):
            texts.append(f.read_text(encoding='utf-8'))
            if args.limit and len(texts) >= args.limit:
                break

    if args.dry_run:
        print('dry-run: would embed', len(texts), 'texts on', device)
        return

    # embed in batches and save each batch
    for idx, embs in embed_texts(args.model, texts, args.batch_size, device):
        out_file = outd / f'emb_batch_{idx:06d}.npy'
        np.save(out_file, embs)
        print('wrote', out_file)

if __name__ == '__main__':
    main()
