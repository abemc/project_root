# 演習: Python 基礎

## 演習 1 — ファイルの行カウンター

**目標**: テキストファイルを読み込み、行数・単語数・文字数を集計するスクリプトを作成する。

```
期待される出力例:
  ファイル: sample.txt
  行数  : 42
  単語数: 318
  文字数: 1,842
```

**要件:**
1. コマンドライン引数でファイルパスを受け取る（`sys.argv` または `argparse`）
2. ファイルが存在しない場合は適切なエラーメッセージを表示する
3. 空行はカウントしない（発展: オプションで切り替え可能にする）

---

## 演習 2 — CSV 成績処理

**目標**: 学生の成績データを CSV で読み込み、統計を計算して別の CSV に保存する。

入力 CSV フォーマット (`grades.csv`):
```
name,math,english,science
Alice,88,92,75
Bob,73,65,90
Charlie,95,88,82
```

**要件:**
1. 各生徒の合計点と平均点を計算する
2. 平均点の降順でソートする
3. 結果を `grades_summary.csv` として保存する（`name,total,average,rank` の列を追加）
4. 全体の科目別平均も標準出力に表示する

---

## 演習 3 — JSON 設定ファイルマネージャー

**目標**: JSON 形式の設定ファイルを安全に読み書きするクラスを実装する。

**要件:**
1. `ConfigManager` クラスを実装する
2. `load(path)` — JSON ファイルを読み込む。存在しなければデフォルト値を返す
3. `save(path)` — JSON ファイルに書き込む（インデント付き）
4. `get(key, default=None)` — キーを指定して値を取得する
5. `set(key, value)` — キーと値をセットする
6. 設定変更のたびに `logging` でログを出力する

使用イメージ:
```python
cfg = ConfigManager({"theme": "dark", "max_items": 100})
cfg.load("settings.json")
cfg.set("max_items", 200)
cfg.save("settings.json")
print(cfg.get("theme"))  # "dark"
```

---

## 演習 4 — デコレータの実装

**目標**: 実用的なデコレータを 3 つ実装する。

### 4-1. `@retry(times=3, delay=1.0)`
失敗したら最大 `times` 回リトライし、各リトライ前に `delay` 秒待機するデコレータ。

```python
@retry(times=3, delay=0.5)
def unstable_request():
    import random
    if random.random() < 0.7:
        raise ConnectionError("接続失敗")
    return "成功"
```

### 4-2. `@cache`
引数をキーとして結果をメモ化するデコレータ（`functools.lru_cache` を使わず自作）。

```python
@cache
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)
```

### 4-3. `@validate_types`
関数の型アノテーションをもとに引数の型を実行時チェックするデコレータ。

```python
@validate_types
def add(a: int, b: int) -> int:
    return a + b

add(1, 2)     # OK
add(1, "2")   # TypeError を raise
```

---

## 演習 5 — ロギング付きファイルコピーツール（発展）

**目標**: ディレクトリ内の特定拡張子のファイルを別ディレクトリにコピーするスクリプトを作成する。

**要件:**
1. `pathlib.Path` を使ってディレクトリを走査する
2. コピー開始・完了・エラーを `logging` で記録する（ファイルにも保存）
3. 同名ファイルが存在する場合はタイムスタンプ付きのファイル名にする
4. `argparse` でソースディレクトリ・コピー先ディレクトリ・拡張子を指定できるようにする

```bash
python copy_tool.py --src ./data --dst ./backup --ext .csv .json
```

---

## 提出チェックリスト

- [ ] 各演習を `01_python_basics/` 内の `.py` ファイルまたは `.ipynb` に実装した
- [ ] `python_basics.ipynb` の各セルを実行して出力を確認した
- [ ] `venv` を作成してスクリプトが動作することを確認した
