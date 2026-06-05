"""
01_python_exercises.py — Python 基礎の実行可能演習スクリプト

実行方法:
    python 01_python_exercises.py

各演習は関数として実装されており、末尾の main() で順番に実行されます。
"""
import csv
import json
import logging
import sys
import time
import functools
import inspect
import random
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────
# 演習 1: ファイルの行カウンター
# ──────────────────────────────────────────
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


def exercise_1():
    print("\n" + "=" * 50)
    print("演習 1: ファイルの行カウンター")
    print("=" * 50)

    # テスト用ファイルを一時的に作成
    sample = Path("_sample_ex1.txt")
    sample.write_text(
        "Hello, World!\n\nこれは2行目です。\nPython は素晴らしい。\n\n終わり\n",
        encoding="utf-8",
    )
    lines, words, chars = count_file(sample, skip_empty=True)
    print(f"  行数  : {lines:,}")
    print(f"  単語数: {words:,}")
    print(f"  文字数: {chars:,}")
    sample.unlink()
    print("  ✅ 演習 1 完了")


# ──────────────────────────────────────────
# 演習 2: CSV 成績処理
# ──────────────────────────────────────────
def process_grades(input_path: str, output_path: str):
    students = []
    subjects = []

    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        subjects = [c for c in reader.fieldnames if c != "name"]
        for row in reader:
            scores = {s: int(row[s]) for s in subjects}
            total  = sum(scores.values())
            avg    = total / len(subjects)
            students.append({"name": row["name"], **scores, "total": total, "average": avg})

    students.sort(key=lambda s: s["average"], reverse=True)
    for rank, student in enumerate(students, start=1):
        student["rank"] = rank

    fieldnames = ["name"] + subjects + ["total", "average", "rank"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for s in students:
            writer.writerow({k: s[k] for k in fieldnames})

    return students, subjects


def exercise_2():
    print("\n" + "=" * 50)
    print("演習 2: CSV 成績処理")
    print("=" * 50)

    csv_path = Path("_grades_ex2.csv")
    csv_path.write_text(
        "name,math,english,science\n"
        "Alice,88,92,75\n"
        "Bob,73,65,90\n"
        "Charlie,95,88,82\n",
        encoding="utf-8",
    )

    students, subjects = process_grades(str(csv_path), "_grades_summary.csv")
    for s in students:
        print(f"  #{s['rank']} {s['name']:10s} 合計:{s['total']:3d} 平均:{s['average']:.1f}")

    csv_path.unlink()
    Path("_grades_summary.csv").unlink(missing_ok=True)
    print("  ✅ 演習 2 完了")


# ──────────────────────────────────────────
# 演習 3: JSON 設定ファイルマネージャー
# ──────────────────────────────────────────
class ConfigManager:
    def __init__(self, defaults: dict = None):
        self._data = dict(defaults or {})

    def load(self, path: str) -> "ConfigManager":
        p = Path(path)
        if p.exists():
            with p.open("r", encoding="utf-8") as f:
                self._data.update(json.load(f))
            logger.debug("設定を読み込み: %s", path)
        return self

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        logger.debug("設定を保存: %s", path)

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        old = self._data.get(key)
        self._data[key] = value
        logger.debug("設定変更: %s = %r → %r", key, old, value)


def exercise_3():
    print("\n" + "=" * 50)
    print("演習 3: JSON 設定ファイルマネージャー")
    print("=" * 50)

    cfg_path = "_settings_ex3.json"
    cfg = ConfigManager({"theme": "dark", "max_items": 100})
    cfg.set("max_items", 200)
    cfg.save(cfg_path)

    cfg2 = ConfigManager()
    cfg2.load(cfg_path)
    print(f"  theme    : {cfg2.get('theme')}")
    print(f"  max_items: {cfg2.get('max_items')}")
    Path(cfg_path).unlink()
    print("  ✅ 演習 3 完了")


# ──────────────────────────────────────────
# 演習 4: デコレータの実装
# ──────────────────────────────────────────
def retry(times: int = 3, delay: float = 0.5):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(1, times + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_err = e
                    logger.debug("リトライ %d/%d: %s", attempt, times, e)
                    if attempt < times:
                        time.sleep(delay)
            raise last_err
        return wrapper
    return decorator


def cache(func):
    _cache = {}

    @functools.wraps(func)
    def wrapper(*args):
        if args not in _cache:
            _cache[args] = func(*args)
        return _cache[args]

    wrapper.cache_clear = lambda: _cache.clear()
    return wrapper


def validate_types(func):
    hints  = func.__annotations__
    params = list(inspect.signature(func).parameters.keys())

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        for param, value in zip(params, args):
            if param in hints and not isinstance(value, hints[param]):
                raise TypeError(
                    f"'{param}' は {hints[param].__name__} 型が必要ですが "
                    f"{type(value).__name__} 型が渡されました。"
                )
        return func(*args, **kwargs)
    return wrapper


def exercise_4():
    print("\n" + "=" * 50)
    print("演習 4: デコレータの実装")
    print("=" * 50)

    # retry
    call_count = {"n": 0}

    @retry(times=4, delay=0.0)
    def flaky():
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise RuntimeError("失敗")
        return "成功"

    result = flaky()
    print(f"  retry: {result} （{call_count['n']} 回試行）")

    # cache
    @cache
    def fibonacci(n):
        if n <= 1:
            return n
        return fibonacci(n - 1) + fibonacci(n - 2)

    print(f"  cache: fibonacci(20) = {fibonacci(20)}")

    # validate_types
    @validate_types
    def add(a: int, b: int) -> int:
        return a + b

    print(f"  validate_types: add(3, 4) = {add(3, 4)}")
    try:
        add(1, "2")
    except TypeError as e:
        print(f"  validate_types: TypeError 正しく発生 — {e}")

    print("  ✅ 演習 4 完了")


# ──────────────────────────────────────────
# メイン
# ──────────────────────────────────────────
def main():
    print("=" * 50)
    print("Python 基礎 演習スクリプト")
    print(f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    exercise_1()
    exercise_2()
    exercise_3()
    exercise_4()

    print("\n" + "=" * 50)
    print("すべての演習が完了しました！ 🎉")
    print("=" * 50)


if __name__ == "__main__":
    main()
