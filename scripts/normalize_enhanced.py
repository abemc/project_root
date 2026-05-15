#!/usr/bin/env python3
"""
簡易正規化強化スクリプト
- ［＃...］注記の除去
- ルビ表記（｜本文《ルビ》）の展開/削除（オプション）
- 全角記号の正規化（例：，。→，。）
- 外字マッピングの簡易フック（必要に応じて追加）

使い方:
  python scripts/normalize_enhanced.py --input-dir corpus/normalized --dry-run
"""
from __future__ import annotations
import re
import argparse
from pathlib import Path

# 外字フォールバックマップ（必要に応じて拡張）
GAIJI_MAP = {
    # '󠄀': '〆',
}

# ルール: remove bracketed editorial notes like ［＃...］
RE_NOTE = re.compile(r'\uFF3B\uFF03.*?\uFF3D')  # ［＃...］（全角）
RE_RUBY = re.compile(r'\uFF5C([^\uFF62]+?)\u300A([^\u300A\u300B]+?)\u300B')  # ｜本文《ルビ》の類似
# variant: accept ASCII markers too
RE_RUBY_ALT = re.compile(r'\|([^《]+?)《([^》]+?)》')

def normalize_text(text: str, remove_ruby: bool = True) -> str:
    # 外字マッピング
    for k, v in GAIJI_MAP.items():
        if k in text:
            text = text.replace(k, v)

    # 注記削除
    text = RE_NOTE.sub('', text)

    # ルビ処理
    if remove_ruby:
        text = RE_RUBY.sub(lambda m: m.group(1), text)
        text = RE_RUBY_ALT.sub(lambda m: m.group(1), text)

    # 全角スペースや多重改行の簡易正規化
    text = re.sub(r'\u3000+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text


def process_file(path: Path, dry_run: bool = True) -> str:
    txt = path.read_text(encoding='utf-8')
    out = normalize_text(txt)
    if dry_run:
        return out
    path.write_text(out, encoding='utf-8')
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input-dir', default='corpus/normalized')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--limit', type=int, default=0, help='0=all')
    args = p.parse_args()

    d = Path(args.input_dir)
    if not d.exists():
        print('input dir not found:', d)
        return
    files = list(d.glob('*.txt'))
    if args.limit > 0:
        files = files[: args.limit]
    for f in files:
        try:
            out = process_file(f, dry_run=args.dry_run)
        except Exception as e:
            print('error', f, e)
        else:
            print('processed', f)

if __name__ == '__main__':
    main()
