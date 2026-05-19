# 🎓 AI/LLM知識ゼロから始める学習ロードマップ
## Phase 7 プロジェクト完全理解ガイド

**目的**: LLM・AI基礎知識ゼロの状態から、このプロジェクトを完全に理解し、次のフェーズの改善が実装できるレベルまで到達する

**所要時間**: 4-6週間（自分のペースで）

---

## 📚 Part 1: 基礎概念の理解（1-2週間）

### Week 1.1: AI/LLMの基本概念

#### 学習ゴール
- LLM（大規模言語モデル）とは何か理解する
- RAG（検索増強生成）の基本概念を理解する
- このプロジェクトがなぜこれらの技術を使うのかを理解する

#### 読むべき資料

**1️⃣ 最初に読むドキュメント:**
```
📄 docs/AUTONOMOUS_LLM_BLUEPRINT.md
   → プロジェクト全体の「なぜ」と「何」を理解
   → 各コンポーネントの役割
   → データのフロー
```

**2️⃣ 次に、基本的なファイルを確認:**
```python
# src/rag/llm.py (116行) を読む
# LLMとの通信がシンプルに理解できるはず
# 何が起きるかを把握 → テキスト入力 → LLM処理 → テキスト出力
```

#### 実習: 概念図を描く
- プロジェクトの流れを自分で図で描いてみる
- 特に: **ユーザー入力** → **ドメイン判定** → **検索** → **応答** のフロー

---

### Week 1.2: ドメイン分類の理解

#### 学習ゴール
- このプロジェクトの「5つのドメイン」が何かを理解する
- ドメイン分類の仕組みを理解する

#### 実習課題1: ドメインの詳細を学ぶ

```bash
# ターミナルでこれを実行して、各ドメインが何か確認する
cd /home/abemc/project_root
python3 << 'EOF'
import sys
sys.path.insert(0, 'src')
from self_improvement.domain_knowledge import DomainKnowledgeManager

dm = DomainKnowledgeManager()

print("=" * 80)
print("【5つの専門ドメイン詳細】")
print("=" * 80)

for domain_name in ["medical", "legal", "business", "technical", "science"]:
    domain = dm.domains.get(domain_name)
    if domain:
        print(f"\n📌 {domain_name.upper()}")
        print(f"   説明: {domain.description}")
        print(f"   キーワード数: {len(domain.keywords)}")
        print(f"   サンプルキーワード: {list(domain.keywords)[:10]}")

print("\n" + "=" * 80)
EOF
```

#### 読むべきコード

```python
# src/self_improvement/domain_knowledge.py を開く
# 特に注目するセクション：
#
# Lines 75-115:
#   ├─ medical_domain定義
#   ├─ legal_domain定義
#   ├─ business_domain定義
#   ├─ technical_domain定義
#   └─ science_domain定義
#
# 各ドメインに含まれるキーワードを読んで、
# なぜそのキーワードが重要かを考える
```

#### 実習課題2: ドメイン推定のテスト

```bash
cd /home/abemc/project_root
python3 << 'EOF'
import sys
sys.path.insert(0, 'src')
from self_improvement.domain_knowledge import DomainKnowledgeManager

dm = DomainKnowledgeManager()

# テストクエリ例
queries = [
    "患者の治療方針について",           # medical
    "知的財産権の登録方法",             # legal
    "デジタルトランスフォーメーション戦略",  # business
    "クラウドインフラの構築",           # technical
    "機械学習モデルの精度評価",         # science
]

print("ドメイン推定テスト\n")
for query in queries:
    domain, confidence = dm.infer_domain_from_query(query)
    print(f"Q: {query}")
    print(f"   推定ドメイン: {domain} (信頼度: {confidence:.1%})\n")
EOF
```

**質問を自分に問いかけてみる:**
- なぜそのドメインに推定されたか？
- キーワードマッチはどのようにされているか？
- 複数のドメインの特徴があるクエリではどうなるか？

---

## 📚 Part 2: コアアルゴリズムの理解（2週間）

### Week 2.1: ドメイン推定アルゴリズム

#### 学習ゴール
- クエリからドメインを推定する仕組みの詳細を理解する
- なぜこのアルゴリズムは100%の精度を達成したのかを理解する

#### 読むべきコード

```python
# src/self_improvement/domain_knowledge.py を詳細に読む

# ★ 必須読み取りセクション: Lines 140-300
#   infer_domain_from_query() メソッド
#
# このメソッドの構造を理解する:
#
# 1. キーワード検出フェーズ
#    - 各ドメインのキーワードをスキャン
#    - マッチ数をカウント
#
# 2. Crossover(複合)検出フェーズ
#    - IP+Business → Legal優先
#    - Analysis+Tech → Business優先  
#    - Tech+Energy+Science → Science優先
#
# 3. スコアリング・ランキング
#    - 各ドメインにスコアを付与
#    - 最高スコアのドメインを返す
```

#### 実習課題3: アルゴリズムのステップバイステップ追跡

```bash
cd /home/abemc/project_root
python3 << 'EOF'
import sys
sys.path.insert(0, 'src')
from self_improvement.domain_knowledge import DomainKnowledgeManager

dm = DomainKnowledgeManager()

# ステップまでを詳細に追跡できるテスト
test_query = "知的財産権とビジネス戦略の統合"

print("=" * 80)
print(f"【クエリ: {test_query}】")
print("=" * 80)
print("\n推定結果:")

domain, confidence = dm.infer_domain_from_query(test_query)
print(f"Result: {domain} (confidence: {confidence:.1%})")

print("\n分析:")
print("このクエリには以下の要素が含まれています:")
print("  1. 知的財産権 → Legal要素")
print("  2. ビジネス戦略 → Business要素")
print("  → これはCrossover(複合)ケース")
print("  → なぜLegalが選ばれたのか、アルゴリズムを追跡してみてください")

EOF
```

#### 🔍 理解を深める質問

1. **キーワード検索の仕組み**
   - Pythonの文字列検索はどう実装されているか？
   - `in` 演算子の使用例を探す

2. **複合(Crossover)検出**
   - IP+Businessの場合、なぜLegalが優先されるか？
   - 複合検出ルールはどこで定義されているか？

3. **スコアリング**
   - スコアの計算式は何か？
   - なぜ100%の精度が達成できたのか？

---

### Week 2.2: 知識統合・推論エンジン

#### 学習ゴール
- MAルチドメイン知識をどのように統合するか理解する
- 因果関係をどのように処理するか理解する

#### 読むべきコード

```python
# src/self_improvement/reasoning_engine.py (467行)
#
# ★ コアクラス: KnowledgeIntegrator
#
# 役割: 異なるドメインから取得した知識を1つの
#      一貫した回答に統合する
#
# 処理フロー:
#   1. マルチドメイン知識入力
#   2. ドメイン間の矛盾検出
#   3. 優先度付け
#   4. 統合知識出力
```

#### 実習課題4: 知識統合のテスト

```bash
cd /home/abemc/project_root
python3 << 'EOF'
import sys
sys.path.insert(0, 'src')

# KnowledgeIntegratorの動作を理解
# (実装ファイルを確認して、テスト可能な例を実行)

print("知識統合エンジンの理解")
print("=" * 80)
print("\n複数ドメインの知識が関連する質問の場合:")
print("  例: 「医療技術での知的財産保護」")
print("  → Medical + Technical + Legal の知識が必要")
print("  → これらをどのように統合するのか？")
print("\nコード:reasoning_engine.py内の")
print("  KnowledgeIntegrator クラスを読んでください")

EOF
```

---

## 📚 Part 3: RAGシステムの理解（1-2週間）

### Week 3.1: RAG (Retrieval-Augmented Generation) の仕組み

#### 学習ゴール
- LLMが質問に答える時、どのように知識ベースを活用するか理解する
- 「検索 + 生成」の流れを理解する

#### 概念図

```
ユーザーの質問
    ↓
【検索フェーズ】
  1. query_preprocessor: 質問を整形・拡張
  2. context_analyzer: 文脈・隠れた意図を分析
  3. domain_knowledge: ドメインを推定
  4. optimized_retriever: 関連ドキュメントを検索
    ↓
【統合フェーズ】
  1. knowledge_integration_engine: 検索結果を統合
  2. reasoning_engine: 因果関係や不確実性を処理
    ↓
【生成フェーズ】
  1. agent (LLM): 統合知識を使ってLLMに指示を出す
  2. LLM: 最終回答を生成
    ↓
最終回答
```

#### 読むべきコード（優先度順）

```python
# ★ Step 1: rag/query_preprocessor.py を読む
#   役割: 質問の前処理
#   - 言語検出
#   - クエリ拡張
#   - ノーマライズ

# ★ Step 2: rag/optimized_retriever.py を読む
#   役割: 最適化された検索
#   - ドメイン別の検索戦略
#   - FAISSインデックスの使用

# ★ Step 3: rag/knowledge_integration_engine.py を読む
#   役割: 検索結果の統合
#   - 複数ドメインの結果を1つにまとめる

# ★ Step 4: rag/agent.py を読む（最後）
#   役割: エンドツーエンドのフロー制御
#   - 全流れの統括
```

### Week 3.2: 本番環境の管理

#### 学習ゴール
- システムがどのように本番環境で監視されているか理解する
- ログ・エラーハンドリングの仕組みを理解する

#### 読むべきコード

```python
# src/rag/production_manager.py (483行)
#   - ロギング
#   - エラーハンドリング
#   - パフォーマンス監視
#   - アラート

# src/self_improvement/scheduler.py (692行)
#   - 自動スケジューリング
#   - リソース管理
```

---

## 🧪 Part 4: 実践テスト & 検証（1週間）

### Week 4.1: テストスイートの実行と理解

#### テストの実行

```bash
cd /home/abemc/project_root

# ★ Phase 7統合テスト（最も重要）
python -m pytest tests/test_phase7_integration.py -v

# ① ドメイン知識テスト
python -m pytest tests/test_self_improvement.py -v

# ② 個別機能テスト
python -m pytest tests/test_phase7.py -v

# ③ マルチモーダルテスト
python -m pytest tests/test_multimodal.py -v
```

#### テストから学ぶべきこと

各テストファイルを開いて、以下を確認してください：

```python
# tests/test_phase7_integration.py を開く
#
# 学ぶべきポイント:
# 1. テストケースの構造
# 2. 各テストが何をテストしているのか
# 3. Expected Output (期待値)
# 4. Actual Output (実際の結果)
#
# 注目すべきテスト:
# - test_domain_inference() 
#   → ドメイン推定が正確か確認
# - test_crossover_detection()
#   → 複合ドメインが正確に検出されるか確認
# - test_integration_pipeline()
#   → エンドツーエンドの流れが動作するか確認
```

#### 実習課題5: テストの改造

```bash
# tests/test_phase7_integration.py をコピーして
# 自分用のテストを追加してみる

# 例:
# - 新しいテストクエリを追加
# - 異なるドメインの組み合わせをテスト
# - アルゴリズムの限界を探す

cp tests/test_phase7_integration.py tests/test_my_custom.py

# エディタで tests/test_my_custom.py を開いて
# カスタムテストケースを追加してから実行
python -m pytest tests/test_my_custom.py -v
```

---

## 📊 Part 5: 深掘り学習（オプション、2-3週間）

### Advanced Topic 1: エンベッディング & ベクトル検索

```python
# src/embeddings/embedding.py を学ぶ
# BGE-M3モデルとは何か
# テキストがどのようにベクトル化されるか
# FAISSインデックスでの高速検索

実習: embeddings/inspection_tools.py でインデックスを確認
```

### Advanced Topic 2: チャンケーション（テキスト分割）

```python
# src/corpus/chunk_text.py を学ぶ
# 長いドキュメントをどのように小分けにするのか
# チャンクサイズと重複度の調整

実習: 自分でテキストを分割してみる
```

### Advanced Topic 3: プロンプト最適化

```python
# src/self_improvement/prompt_optimizer.py を学ぶ
# rag/prompts.py でプロンプトテンプレートを確認
# LLMへの指示がどのように最適化されるのか

実習: 新しいプロンプトテンプレートを作成
```

---

## ✅ 学習チェックリスト

### Phase 1: 基本概念 (完了時間: ___ 日)
- [ ] AUTONOMOUS_LLM_BLUEPRINT を読んだ
- [ ] 5つのドメインが何か説明できる
- [ ] RAGの基本フローが図で描ける
- [ ] ドメイン推定のテストを実行した

### Phase 2: コアアルゴリズム (完了時間: ___ 日)
- [ ] ドメイン推定アルゴリズムを読み終わった
- [ ] Crossover検出の仕組みが理解できた
- [ ] KnowledgeIntegratorの役割が説明できる
- [ ] 簡単なテストクエリで精度を確認した

### Phase 3: RAGシステム (完了時間: ___ 日)
- [ ] query_preprocessor → optimized_retriever の流れが理解できた
- [ ] knowledge_integration_engine の役割が理解できた
- [ ] agent.py の全体フローを追跡できた
- [ ] production_manager の監視機能が理解できた

### Phase 4: 実践テスト (完了時間: ___ 日)
- [ ] test_phase7_integration.py を実行した
- [ ] テストケースの構造を理解した
- [ ] カスタムテストを1つ作成・実行した
- [ ] テスト結果の意味が理解できた

### Advanced (オプション) (完了時間: ___ 日)
- [ ] エンベッディングの仕組みが理解できた
- [ ] テキストチャンケーションを実装できた
- [ ] プロンプト最適化の方法が理解できた

---

## 🎯 各フェーズ終了時の「できること」

### ✅ Phase 1終了時
- このプロジェクトが「何をするのか」を説明できる
- AIとLLMの基本的な概念が理解できている
- RAGとはどんな技術かが説明できる

### ✅ Phase 2終了時
- ドメイン推定アルゴリズムが完全に理解できている
- なぜ100%の精度が達成できたかが説明できる
- Crossover検出の価値が理解できている

### ✅ Phase 3終了時
- クエリから最終回答までの全フローが図で説明できる
- 各コンポーネントの役割が正確に説明できる
- 本番環境での監視・ログの仕組みが理解できている

### ✅ Phase 4終了時
- テストコードを書いて実行できる
- バグを見つけて修正できる
- 新機能を追加できる準備ができている

---

## 🚀 学習後のNEXT STEP

このロードマップを完了すれば、以下が可能になります：

1. **新規ドメインの追加**
   - 心理学ドメインを追加してみる
   - 社会科学ドメインを追加してみる

2. **アルゴリズムの改善**
   - 複合(Crossover)検出ルールの最適化
   - スコアリング方法の改善

3. **パフォーマンス最適化**
   - 応答時間の短縮
   - メモリ使用量の削減

4. **UI/UX改善**
   - Streamlitダッシュボードの強化
   - ユーザーフィードバックインターフェースの作成

5. **継続的学習の実装**
   - ユーザーフィードバックからの自動学習
   - A/Bテストの実装

---

## 💡 学習中の重要なヒント

### Tip 1: 「なぜ？」を常に問いかける
```
コードを読むときは常に:
"このコードは何をしているのか？"
"なぜこの方法を使うのか？"
"別の方法はないのか？"
と問いかけてください
```

### Tip 2: 常に実験する
```
理解が曖昧な部分は:
- 対象コードをコピーして修正
- テストを実行して動作確認
- 出力結果を分析
する習慣をつけてください
```

### Tip 3: ドキュメント作成
```
各フェーズを完了したら、
自分用のドキュメントを作成してください:
- そのフェーズで何を学んだか
- 重要な概念
- 次への繋がり

これが将来の参照資料になります
```

### Tip 4: コミュニティに質問する
```
わからないことがあったら:
1. ドキュメント・コメントを再読
2. APIドキュメントを参照
3. テストコードから学ぶ
4. 私に質問する
という順で進めてください
```

---

## 🗺️ 全体マップ

```
START: AI/LLM知識ゼロ
   ↓
WEEK 1-2: 基本概念
   → 理解: LLM, RAG, ドメイン分類
   → テスト: ドメイン推定の確認
   ↓
WEEK 2-3: コアアルゴリズム  
   → 理解: ドメイン推定, 知識統合
   → テスト: アルゴリズムのトレース
   ↓
WEEK 3-4: RAGシステム
   → 理解: 検索→統合→生成フロー
   → テスト: 全体統合テスト実行
   ↓
WEEK 5: 実践テスト
   → 理解: テストコード構造
   → テスト: カスタムテスト実装
   ↓
ADVANCED: 深掘り学習 (オプション)
   → エンベッディング, チャンケーション, プロンプト最適化
   ↓
GOAL: 新機能実装・アルゴリズム改善できるレベル
```

---

## 📞 サポート

学習中に困ったら、このファイルと一緒に質問してください：
- 理解を深めるための質問
- テストの失敗についての質問
- コードの改造についての質問
- 次のステップについての質問

**学習成功をお祈りしています！** 🎉

---

*作成日: 2026-04-12*
*更新日: 2026-04-12*
*バージョン: 1.0*
