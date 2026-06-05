# Python 基礎ノート

## 1. 変数とデータ型

Python は動的型付け言語です。変数を宣言するだけで型が決まります。

```python
# 基本的な型
x = 42           # int
y = 3.14         # float
name = "Alice"   # str
flag = True      # bool
nothing = None   # NoneType

# 型確認
print(type(x))   # <class 'int'>
```

### コレクション型

| 型 | 特徴 | 例 |
|---|---|---|
| `list` | 順序あり・変更可 | `[1, 2, 3]` |
| `tuple` | 順序あり・変更不可 | `(1, 2, 3)` |
| `dict` | キーと値のペア | `{"a": 1}` |
| `set` | 重複なし・順序なし | `{1, 2, 3}` |

```python
# リストの基本操作
fruits = ["apple", "banana", "cherry"]
fruits.append("date")       # 追加
fruits.pop(0)               # 先頭を削除して返す
fruits[1:3]                 # スライス → ["cherry", "date"]

# 辞書の基本操作
person = {"name": "Alice", "age": 30}
person["email"] = "alice@example.com"  # 追加
person.get("phone", "N/A")             # 安全なアクセス → "N/A"
```

---

## 2. 制御構造

### 条件分岐

```python
score = 75

if score >= 90:
    grade = "A"
elif score >= 70:
    grade = "B"
else:
    grade = "C"

# 三項演算子
grade = "合格" if score >= 60 else "不合格"
```

### ループ

```python
# for ループ
for i in range(5):           # 0, 1, 2, 3, 4
    print(i)

for fruit in ["apple", "banana"]:
    print(fruit)

# enumerate でインデックスも取得
for i, fruit in enumerate(["apple", "banana"], start=1):
    print(f"{i}: {fruit}")

# while ループ
count = 0
while count < 5:
    count += 1

# リスト内包表記 (list comprehension)
squares = [x**2 for x in range(10)]
evens   = [x for x in range(20) if x % 2 == 0]
```

---

## 3. 関数

```python
# 基本的な関数定義
def greet(name: str, greeting: str = "こんにちは") -> str:
    """挨拶文を返す関数。"""
    return f"{greeting}、{name}さん！"

print(greet("Alice"))               # こんにちは、Aliceさん！
print(greet("Bob", "おはよう"))     # おはよう、Bobさん！

# *args と **kwargs
def summarize(*args, **kwargs):
    print("位置引数:", args)
    print("キーワード引数:", kwargs)

summarize(1, 2, 3, name="Alice", age=30)
```

### ラムダ式

```python
double = lambda x: x * 2
print(double(5))   # 10

# sorted() のキー指定に便利
words = ["banana", "apple", "cherry"]
sorted_words = sorted(words, key=lambda w: len(w))
```

### デコレータ

デコレータは関数を受け取り、拡張した関数を返す高階関数です。

```python
import time
import functools

def timer(func):
    """実行時間を計測するデコレータ。"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"{func.__name__} の実行時間: {elapsed:.4f}秒")
        return result
    return wrapper

@timer
def slow_sum(n):
    return sum(range(n))

slow_sum(1_000_000)
```

---

## 4. モジュールとパッケージ

```python
# 標準ライブラリのインポート
import os
import sys
from pathlib import Path
from datetime import datetime

# 自作モジュールのインポート
# my_module.py が同ディレクトリにある場合
from my_module import my_function

# パッケージ構造の例
# my_package/
#   __init__.py
#   utils.py
#   models.py
from my_package.utils import helper
```

---

## 5. 仮想環境とパッケージ管理

```bash
# 仮想環境の作成と有効化
python -m venv .venv
source .venv/bin/activate       # Linux/macOS
# .venv\Scripts\activate        # Windows

# パッケージのインストール
pip install numpy pandas

# 依存関係の保存と復元
pip freeze > requirements.txt
pip install -r requirements.txt
```

---

## 6. ファイル操作

### テキストファイル

```python
# 書き込み
with open("output.txt", "w", encoding="utf-8") as f:
    f.write("Hello, World!\n")

# 読み込み
with open("output.txt", "r", encoding="utf-8") as f:
    content = f.read()          # 全体を文字列で
    lines = f.readlines()       # 行のリストで
```

### CSV

```python
import csv

# 書き込み
rows = [["name", "age"], ["Alice", 30], ["Bob", 25]]
with open("people.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerows(rows)

# 読み込み
with open("people.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        print(row["name"], row["age"])
```

### JSON

```python
import json

data = {"name": "Alice", "scores": [95, 88, 72]}

# 書き込み
with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# 読み込み
with open("data.json", "r", encoding="utf-8") as f:
    loaded = json.load(f)
print(loaded["scores"])  # [95, 88, 72]
```

---

## 7. デバッグとロギング

```python
import logging

# ロガーの設定
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

logger.debug("デバッグ情報")
logger.info("処理開始")
logger.warning("注意が必要な状況")
logger.error("エラーが発生")
logger.critical("致命的なエラー")
```

### ファイルへのロギング

```python
import logging
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
)
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

logger = logging.getLogger("myapp")
logger.setLevel(logging.INFO)
logger.addHandler(handler)
```

---

## チェックポイント確認

- [ ] 変数・リスト・辞書を使った簡単なスクリプトが書ける
- [ ] for ループとリスト内包表記を使い分けられる
- [ ] 関数・デコレータを定義して使える
- [ ] venv を作成して pip でパッケージを管理できる
- [ ] CSV・JSON ファイルを読み書きできる
- [ ] logging モジュールでログを出力できる
