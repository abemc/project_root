# 模範解答: Python 基礎

## 演習 1 — ファイルの行カウンター

```python
# word_count.py
import sys
import argparse
from pathlib import Path


def count_file(path: Path, skip_empty: bool = True):
    """テキストファイルの行数・単語数・文字数を返す。"""
    if not path.exists():
        raise FileNotFoundError(f"ファイルが見つかりません: {path}")

    lines = words = chars = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            stripped = line.rstrip("\n")
            if skip_empty and stripped.strip() == "":
                continue
            lines += 1
            words += len(stripped.split())
            chars += len(stripped)
    return lines, words, chars


def main():
    parser = argparse.ArgumentParser(description="テキストファイルを集計します。")
    parser.add_argument("file", type=Path, help="対象ファイル")
    parser.add_argument("--no-skip-empty", action="store_true",
                        help="空行もカウントする")
    args = parser.parse_args()

    lines, words, chars = count_file(args.file, not args.no_skip_empty)
    print(f"ファイル: {args.file}")
    print(f"  行数  : {lines:,}")
    print(f"  単語数: {words:,}")
    print(f"  文字数: {chars:,}")


if __name__ == "__main__":
    main()
```

---

## 演習 2 — CSV 成績処理

```python
# grades.py
import csv
from pathlib import Path


def process_grades(input_path: str = "grades.csv",
                   output_path: str = "grades_summary.csv"):
    subjects = []
    students = []

    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        subjects = [col for col in reader.fieldnames if col != "name"]
        for row in reader:
            scores = {s: int(row[s]) for s in subjects}
            total = sum(scores.values())
            avg   = total / len(subjects)
            students.append({"name": row["name"], **scores,
                              "total": total, "average": avg})

    # 平均点の降順でソート
    students.sort(key=lambda s: s["average"], reverse=True)
    for rank, student in enumerate(students, start=1):
        student["rank"] = rank

    # 結果を保存
    fieldnames = ["name"] + subjects + ["total", "average", "rank"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for s in students:
            writer.writerow({k: s[k] for k in fieldnames})

    # 科目別平均を表示
    print("=== 科目別平均 ===")
    for subj in subjects:
        avg = sum(s[subj] for s in students) / len(students)
        print(f"  {subj}: {avg:.1f}")
    print(f"\n結果を {output_path} に保存しました。")


if __name__ == "__main__":
    process_grades()
```

---

## 演習 3 — JSON 設定ファイルマネージャー

```python
# config_manager.py
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")


class ConfigManager:
    def __init__(self, defaults: dict = None):
        self._data = dict(defaults or {})

    def load(self, path: str) -> "ConfigManager":
        p = Path(path)
        if p.exists():
            with p.open("r", encoding="utf-8") as f:
                self._data.update(json.load(f))
            logger.info("設定を読み込みました: %s", path)
        else:
            logger.warning("設定ファイルが存在しません。デフォルト値を使用: %s", path)
        return self

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        logger.info("設定を保存しました: %s", path)

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        old = self._data.get(key)
        self._data[key] = value
        logger.info("設定変更: %s = %r → %r", key, old, value)


# 使用例
if __name__ == "__main__":
    cfg = ConfigManager({"theme": "dark", "max_items": 100})
    cfg.load("settings.json")
    cfg.set("max_items", 200)
    cfg.save("settings.json")
    print(cfg.get("theme"))
```

---

## 演習 4 — デコレータの実装

```python
# decorators.py
import time
import functools
import inspect


# 4-1. retry デコレータ
def retry(times: int = 3, delay: float = 1.0):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(1, times + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_err = e
                    print(f"[retry] 試行 {attempt}/{times} 失敗: {e}")
                    if attempt < times:
                        time.sleep(delay)
            raise last_err
        return wrapper
    return decorator


# 4-2. cache デコレータ
def cache(func):
    _cache = {}
    @functools.wraps(func)
    def wrapper(*args):
        if args not in _cache:
            _cache[args] = func(*args)
        return _cache[args]
    wrapper.cache_clear = lambda: _cache.clear()
    return wrapper


# 4-3. validate_types デコレータ
def validate_types(func):
    hints = func.__annotations__
    params = list(inspect.signature(func).parameters.keys())

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        for param, value in zip(params, args):
            if param in hints and not isinstance(value, hints[param]):
                raise TypeError(
                    f"引数 '{param}' は {hints[param].__name__} 型が必要ですが、"
                    f"{type(value).__name__} 型が渡されました。"
                )
        return func(*args, **kwargs)
    return wrapper


# --- 動作確認 ---
if __name__ == "__main__":
    import random

    @retry(times=3, delay=0.1)
    def unstable():
        if random.random() < 0.6:
            raise ConnectionError("失敗")
        return "成功"

    @cache
    def fibonacci(n):
        if n <= 1:
            return n
        return fibonacci(n - 1) + fibonacci(n - 2)

    @validate_types
    def add(a: int, b: int) -> int:
        return a + b

    print(fibonacci(10))  # 55
    print(add(3, 4))      # 7
    try:
        add(1, "2")
    except TypeError as e:
        print(e)
```

---

## 演習 5 — ロギング付きファイルコピーツール（発展）

```python
# copy_tool.py
import argparse
import logging
import shutil
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(log_file: str = "copy_tool.log") -> logging.Logger:
    logger = logging.getLogger("copy_tool")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    ch.setLevel(logging.INFO)

    fh = RotatingFileHandler(log_file, maxBytes=500_000, backupCount=2, encoding="utf-8")
    fh.setFormatter(fmt)
    fh.setLevel(logging.DEBUG)

    logger.addHandler(ch)
    logger.addHandler(fh)
    return logger


def unique_path(dst: Path) -> Path:
    if not dst.exists():
        return dst
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return dst.with_stem(f"{dst.stem}_{ts}")


def copy_files(src: Path, dst: Path, extensions: list[str], logger: logging.Logger):
    dst.mkdir(parents=True, exist_ok=True)
    files = [f for ext in extensions for f in src.rglob(f"*{ext}")]
    logger.info("コピー開始: %d ファイルを %s → %s", len(files), src, dst)

    success = error = 0
    for file in files:
        dest_file = unique_path(dst / file.name)
        try:
            shutil.copy2(file, dest_file)
            logger.debug("コピー完了: %s → %s", file, dest_file)
            success += 1
        except Exception as e:
            logger.error("コピー失敗: %s — %s", file, e)
            error += 1

    logger.info("完了: 成功 %d / エラー %d", success, error)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ファイルコピーツール")
    parser.add_argument("--src", type=Path, required=True, help="ソースディレクトリ")
    parser.add_argument("--dst", type=Path, required=True, help="コピー先ディレクトリ")
    parser.add_argument("--ext", nargs="+", default=[".csv", ".json"],
                        help="対象拡張子 (例: .csv .json)")
    args = parser.parse_args()

    log = setup_logger()
    copy_files(args.src, args.dst, args.ext, log)
```
