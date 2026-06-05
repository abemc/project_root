# 演習: AI 倫理・安全

## 演習 1 — プライバシーリスクの特定

以下のデータ処理フローに含まれるプライバシーリスクをすべて特定し、対策を提案してください。

**シナリオ**: 医療機関が AI チャットボットを開発している。

```
[収集フロー]
患者が症状を入力
  → フルテキストを OpenAI API に送信（サードパーティ）
  → レスポンスをデータベースに保存（患者 ID・タイムスタンプ付き）
  → モデル改善のために過去 5 年分の会話ログを訓練データに使用
  → 精度向上のため看護師がラベル付け（患者名は非表示だが症状・日付は残る）

[共有]
  → 研究機関にデータセット（氏名削除済み）を提供
```

**質問:**
1. 上記フローに含まれるプライバシーリスクを少なくとも 5 つ挙げる
2. 各リスクに対する技術的・組織的対策を提案する
3. `checklist.md` のフェーズ 1 に沿ってこのフローを評価する

---

## 演習 2 — バイアス検出と公平性評価

**目標**: 架空の採用スクリーニングモデルのバイアスを検出する。

```python
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

np.random.seed(42)
n = 1000

# 特徴量: 経験年数・スキルスコア・学歴
experience = np.random.uniform(0, 15, n)
skill      = np.random.uniform(0, 100, n)
education  = np.random.randint(1, 4, n)        # 1=高卒, 2=大卒, 3=大学院

# 保護属性: 性別（0=男性, 1=女性）
gender = np.random.randint(0, 2, n)

# 意図的にバイアスを含めたラベル（女性は同じスキルでも採用されにくい）
log_odds = 0.3*experience + 0.05*skill + 0.5*education - 0.8*gender
prob = 1 / (1 + np.exp(-log_odds + 2))
y = (np.random.uniform(0, 1, n) < prob).astype(int)

X = np.column_stack([experience, skill, education])
```

**要件:**
1. `X` を特徴量として `LogisticRegression` を訓練する（`gender` は含めない）
2. 男女それぞれの合格率（陽性率）を計算する（Demographic Parity の確認）
3. `notes.md` の `fairness_metrics` 関数を使って TPR・FPR を比較する
4. バイアスが存在することを定量的に示し、その原因（代理変数）を考察する
5. **発展**: `gender` を除いた場合でもバイアスが残る理由を説明する

---

## 演習 3 — 差分プライバシーの実験

**目標**: ε（プライバシー予算）が統計の精度とプライバシー保護のトレードオフに与える影響を実験する。

```python
import numpy as np

# 架空の年齢データ（正規分布）
np.random.seed(0)
ages = np.random.normal(loc=35, scale=10, size=1000).clip(18, 80)
true_mean = ages.mean()

def laplace_mechanism(value: float, sensitivity: float, epsilon: float) -> float:
    return value + np.random.laplace(0, sensitivity / epsilon)
```

**要件:**
1. ε = [0.01, 0.1, 0.5, 1.0, 5.0, 10.0] で 100 回ずつランダムノイズを加える
2. 各 ε について推定値の平均誤差（MAE）を計算する
3. ε と MAE の関係をグラフ化する
4. 「プライバシー保護が強い（ε 小）」と「精度が高い（ε 大）」のトレードオフを図で示す
5. 医療データの場合に適切な ε の値を選ぶ基準を考察する

---

## 演習 4 — LLM のリスク評価（発展）

**目標**: LLM の出力に含まれる潜在的なリスクを分類・対策する。

以下の LLM 出力例を読んで、各リスクを分類してください:

```
ユーザー: 効果的なダイエット方法を教えて
AI出力A: "断食して水だけ飲めば1週間で5kg痩せます。医者に診せる必要はありません。"

ユーザー: 2024年のオリンピック開催地は？
AI出力B: "2024年のオリンピックはパリで開催され、日本は金メダル10個を獲得しました。"
（実際の金メダル数と異なる可能性がある）

ユーザー: 私の個人情報を教えて
AI出力C: "あなたの名前はAさん、住所は東京都..."
（ユーザーが提供していない情報を生成）
```

**要件:**
1. 各出力のリスク種別（ハルシネーション・有害コンテンツ・プライバシー侵害など）を特定する
2. 各リスクに対するシステム設計上の対策を提案する
3. プロンプトエンジニアリングでリスクを軽減するシステムプロンプトを設計する

---

## 提出チェックリスト

- [ ] `checklist.md` を使って演習 1 のシナリオを評価した
- [ ] `fairness_metrics` を実装してバイアスを定量化できた
- [ ] 差分プライバシーのε-精度トレードオフをグラフで表現できた
- [ ] LLM のリスクを 3 つ以上の種別に分類できた
