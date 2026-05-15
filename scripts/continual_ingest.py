#!/usr/bin/env python3
"""
継続インジェストのスケルトン
- 監視フォルダ(`corpus/uploads`)に新ファイルが来たら処理を行い、
  正規化 -> 埋め込み -> VectorStore (Chroma/FAISS) に追加する想定
- 本スクリプトはワークフローのスケルトンとして、実運用では例外処理/並列化/トランザクション管理を追加してください.

Usage:
  python scripts/continual_ingest.py --watch-dir corpus/uploads --once
"""
from __future__ import annotations
import argparse
from pathlib import Path
import time
import subprocess


def process_file(path: Path):
    print('process', path)
    # 1) normalize (call normalize_enhanced)
    subprocess.run(['python', 'scripts/normalize_enhanced.py', '--input-dir', str(path.parent), '--dry-run'])
    # 2) embed (call async_embed as a blocking step for now)
    subprocess.run(['python', 'scripts/async_embed.py', '--source', str(path), '--batch-size', '64', '--device', 'auto', '--out-dir', 'corpus/embeddings'])
    # 3) optional: call existing ingest scripts or API to add to Chroma/FAISS
    print('TODO: add to Chroma/FAISS via existing scripts')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--watch-dir', default='corpus/uploads')
    ap.add_argument('--interval', type=int, default=10)
    ap.add_argument('--once', action='store_true')
    args = ap.parse_args()

    d = Path(args.watch_dir)
    d.mkdir(parents=True, exist_ok=True)
    seen = set()
    for f in d.iterdir():
        seen.add(f.name)

    try:
        while True:
            for f in sorted(d.iterdir()):
                if f.name in seen:
                    continue
                process_file(f)
                seen.add(f.name)
            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print('stopping')

if __name__ == '__main__':
    main()
