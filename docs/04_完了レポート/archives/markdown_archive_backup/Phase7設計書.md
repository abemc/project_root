# Phase 7: マルチドメイン知識管理・文脈深化エンジン

**日付**: 2026-04-11  
**バージョン**: 1.0  
**ステータス**: 設計フェーズ

---

## 📋 概要

**目標**: さまざまな分野（医学、法律、技術、ビジネス等）の知識を保持し、高度な文脈理解能力を持つシステムへの進化

**前提**: Phase 1-6 で実装された完全自立型LLM $(12/12 \text{ PASS})$ をベースに、以下の3つのメインコンポーネントを追加

---

## 🎯 主要実装目標

### 目標1: マルチドメイン知識管理
- ✅ 複数分野の知識を体系化・分類
- ✅ ドメイン間の関連性を管理
- ✅ ドメイン固有の文脈を保持

### 目標2: 文脈理解の深化
- ✅ 質問の直接的意図 + 隠れた意図を理解
- ✅ ユーザーの知識レベルを推定
- ✅ 会話の背景情報を追跡

### 目標3: 知識統合・推論
- ✅ 複数ドメイン知識の関連付け
- ✅ 因果関係・相関関係を分析
- ✅ 不確実性を考慮した推論

---

## 🏗️ アーキテクチャ設計

```
┌─────────────────────────────────────────────────────────────┐
│                  ユーザークエリ入力                         │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│                 文脈分析レイヤー                             │
├─────────────────────────────────────────────────────────────┤
│ • ContextAnalyzer: 質問文の背景分析                         │
│ • ImplicitIntentDetector: 隠れた意図検出                    │
│ • MetaContextTracker: ユーザー知識状態追跡                  │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              マルチドメイン知識検索レイヤー                  │
├─────────────────────────────────────────────────────────────┤
│ • DomainKnowledgeManager: ドメイン管理                      │
│ • CrossDomainLinker: ドメイン間リンク                       │
│ • DomainIndexer: インデックス検索                           │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│             知識統合・推論レイヤー                           │
├─────────────────────────────────────────────────────────────┤
│ • KnowledgeIntegrator: マルチドメイン統合                   │
│ • CausalReasoningEngine: 因果分析                           │
│ • UncertaintyManager: 不確実性管理                          │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│           推論結果 + 文脈に基づいた回答生成                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 コンポーネント詳細設計

### 1. 文脈分析レイヤー

#### 1.1 ContextAnalyzer

**目的**: 質問の直接的・間接的背景を分析

```python
@dataclass
class QueryContext:
    primary_intent: str          # 主要意図
    domain: str                  # 推測ドメイン
    complexity: str              # 複雑性（SIMPLE/MODERATE/COMPLEX）
    information_need: Dict       # 情報需要の分解
    assumed_knowledge: List[str] # 仮定される前知識
    temporal_context: str        # 時間的背景
    
class ContextAnalyzer:
    def analyze_query(query: str, history: List[str]) -> QueryContext
    def extract_information_needs(query: str) -> Dict
    def infer_assumed_knowledge(query: str, domain: str) -> List[str]
    def detect_temporal_references(query: str) -> str
```

#### 1.2 ImplicitIntentDetector

**目的**: 表面上の質問に隠れた意図を検出

```python
@dataclass
class ImplicitIntent:
    explicit: str                # 明示的な意図
    implicit_list: List[str]     # 隠れた意図（複数）
    confidence_scores: Dict      # 各隠れた意図の確実度
    reasoning: str               # 推論理由

class ImplicitIntentDetector:
    def detect(query: str, context: QueryContext) -> ImplicitIntent
    def _extract_emotional_intent(query: str) -> Optional[str]
    def _extract_meta_intent(query: str) -> Optional[str]
    def _extract_clarification_intent(query: str) -> Optional[str]
```

#### 1.3 MetaContextTracker

**目的**: ユーザーの知識状態・過去の会話を追跡

```python
@dataclass
class UserMetaContext:
    knowledge_level: Dict[str, float]  # ドメイン別知識レベル推定（0-1）
    vocabulary_level: str              # 語彙レベル
    conversation_history: List[Dict]   # 会話履歴
    established_facts: Dict            # 既に確認された事実
    misconceptions: List[str]          # 検出された誤解
    preferred_explanation_style: str   # 説明スタイル選好

class MetaContextTracker:
    def update_user_profile(query: str, response: str) -> None
    def infer_knowledge_level(query: str, domain: str) -> float
    def detect_misconceptions(query: str, response: str) -> List[str]
    def get_optimal_explanation_style(domain: str) -> str
```

---

### 2. マルチドメイン知識管理レイヤー

#### 2.1 DomainKnowledgeManager

**目的**: 複数ドメインの知識を登録・管理

```python
@dataclass
class Domain:
    name: str                    # ドメイン名（medical, legal, technical）
    description: str             # 説明
    key_concepts: List[str]      # 主要概念
    prerequisites: List[str]     # 前提知識
    related_domains: List[str]   # 関連ドメイン
    update_frequency: str        # 更新頻度
    last_updated: datetime       # 最終更新日時
    quality_score: float         # 知識品質スコア

class DomainKnowledgeManager:
    def register_domain(domain: Domain) -> None
    def list_domains() -> List[Domain]
    def get_domain(domain_name: str) -> Domain
    def update_domain(domain: Domain) -> None
    def infer_domain_from_query(query: str) -> List[Tuple[str, float]]  # (domain, confidence)
```

#### 2.2 CrossDomainLinker

**目的**: ドメイン間の関連関係を管理・検出

```python
@dataclass
class CrossDomainLink:
    source_domain: str           # ソースドメイン
    target_domain: str           # ターゲットドメイン
    relation_type: str           # 関連タイプ（prerequisite, similar, contrasting）
    bridge_concepts: List[str]   # 架け橋概念
    strength: float              # 関連の強さ（0-1）

class CrossDomainLinker:
    def link_domains(source: str, target: str, relation_type: str) -> CrossDomainLink
    def find_related_domains(domain: str, relation_type: Optional[str] = None) -> List[CrossDomainLink]
    def infer_cross_domain_knowledge(query: str, primary_domain: str) -> List[str]  # 関連知識
    def bridge_knowledge(source_domain: str, target_domain: str) -> List[str]  # 架け橋知識
```

#### 2.3 DomainIndexer

**目的**: ドメイン内知識の効率的検索

```python
class DomainIndexer:
    def index_knowledge(domain: str, concepts: Dict[str, List[str]]) -> None
    def search_in_domain(domain: str, query: str, top_k: int = 5) -> List[KnowledgeItem]
    def get_domain_hierarchy(domain: str) -> Dict  # 概念階層
    def suggest_related_concepts(domain: str, concept: str) -> List[str]
```

---

### 3. 知識統合・推論レイヤー

#### 3.1 KnowledgeIntegrator

**目的**: 複数ドメイン知識を統合して統一的な回答を生成

```python
@dataclass
class IntegratedKnowledge:
    primary_domain: str          # 主要ドメイン
    relevant_domains: List[str]  # 関連ドメイン
    integrated_facts: List[Dict] # 統合された事実
    contradictions: List[Dict]   # 発見された矛盾
    synthesis: str               # 統合的な説明

class KnowledgeIntegrator:
    def integrate_knowledge(primary_domain: str, related_domains: List[str], 
                           query: str) -> IntegratedKnowledge
    def detect_contradictions(domain1: str, domain2: str, topic: str) -> List[Dict]
    def synthesize_answer(integrated: IntegratedKnowledge) -> str
    def explain_perspective_differences(domain1: str, domain2: str, topic: str) -> str
```

#### 3.2 CausalReasoningEngine

**目的**: 因果関係・相関関係を分析

```python
@dataclass
class CausalRelation:
    cause: str                   # 原因
    effect: str                  # 結果
    strength: float              # 因果の強さ
    temporal_lag: Optional[str]  # 時間的ラグ
    conditions: List[str]        # 条件
    confidence: float            # 信頼度

class CausalReasoningEngine:
    def infer_causality(fact1: str, fact2: str) -> Optional[CausalRelation]
    def trace_causality_chain(root_cause: str, max_depth: int = 5) -> List[CausalRelation]
    def identify_confounders(effect: str, domain: str) -> List[str]
    def counterfactual_analysis(scenario: str) -> Dict  # 反事実分析
```

#### 3.3 UncertaintyManager

**目的**: 知識の不確実性を管理・表現

```python
@dataclass
class Uncertainty:
    level: float                 # 不確実性レベル（0-1）
    sources: List[str]           # 不確実性の源（insufficient_data, conflicting_evidence など）
    confidence_interval: Tuple[float, float]  # 信頼区間
    alternative_interpretations: List[str]    # 代替解釈

class UncertaintyManager:
    def assess_uncertainty(statement: str, domain: str) -> Uncertainty
    def express_uncertainty(uncertainty: Uncertainty) -> str  # 不確実性を言語化
    def combine_uncertainties(uncertainties: List[Uncertainty]) -> Uncertainty
    def recommend_additional_research(uncertainty: Uncertainty) -> List[str]
```

---

## 📊 データ構造

### コーパス拡張設計

```yaml
corpus/
├── domains/                    # 新規: ドメイン管理
│   ├── medical.json           # 医学ドメイン定義
│   ├── legal.json             # 法律ドメイン定義
│   ├── technical.json         # 技術ドメイン定義
│   └── business.json          # ビジネスドメイン定義
├── cross_domain_links/        # 新規: ドメイン間リンク
│   ├── medical_legal.json    # 医学-法律 関連
│   ├── technical_business.json # 技術-ビジネス 関連
│   └── ...
├── domain_indices/            # 新規: ドメイン別インデックス
│   ├── medical_index.faiss   
│   ├── legal_index.faiss     
│   └── ...
└── context_profiles/          # 新規: ユーザーコンテキスト
    ├── user_knowledge_profiles.json
    ├── misconception_database.json
    └── conversation_history.jsonl
```

---

## 🔄 ワークフロー

### フロー1: マルチドメイン回答生成

```
ユーザークエリ
    ↓
[ContextAnalyzer] → QueryContext / ImplicitIntent 抽出
    ↓
[DomainKnowledgeManager] → 主要ドメイン + 関連ドメイン推定
    ↓
[CrossDomainLinker] → ドメイン間の知識リンク取得
    ↓
[DomainIndexer] → 各ドメインから知識検索
    ↓
[KnowledgeIntegrator] → 複数ドメイン知識を統合
    ↓
[CausalReasoningEngine] → 因果関係分析
    ↓
[UncertaintyManager] → 不確実性評価
    ↓
統合的な回答生成 + 信頼度表示 + 限界表示
```

### フロー2: 隠れた意図への対応

```
[ImplicitIntentDetector] → 隠れた意図検出 (複数)
    ↓
[MetaContextTracker] → ユーザー知識状態確認
    ↓
明示的意図 + 隠れた意図に応じた説明レベル調整
    ↓
ユーザーの知識レベルに最適な回答生成
```

---

## 📈 期待される改善

| 指標 | 現在 | Phase 7 後 | 改善度 |
|-----|------|----------|--------|
| ドメイン数 | 1（単体） | 5+ | **500%+** |
| 文脈理解の深さ | 5 層 | 8+ 層 | **60%+** |
| 隠れた意図認識率 | 0% | 70%+ | **新規機能** |
| 知識統合の実装 | 無し | 有り | **新規機能** |
| ユーザー知識推定 | なし | 有り | **新規機能** |

---

## 🧪 テスト計画

### テスト 1: マルチドメイン知識管理

```python
def test_domain_registration():
    # 5以上のドメイン登録
    # ドメイン間の関連性リンク作成
    # クロスドメイン検索動作
```

### テスト 2: 文脈理解

```python
def test_context_analysis():
    # 複雑な質問の背景分析
    # 隠れた意図の検出精度（3+意図検出）
    # ユーザー知識レベル推定
```

### テスト 3: 知識統合・推論

```python
def test_knowledge_integration():
    # マルチドメイン知識統合
    # 因果関係推論
    # 不確実性管理
```

### テスト 4: 統合トレーニング

```python
def test_e2e_multimodal_knowledge():
    # 複雑なクロスドメイン質問への対応
    # ユーザー知識状態の更新
    # 段階的説明の生成
```

---

## 📅 実装スケジュール

| Phase | タスク | 期間 | 依存関係 |
|-------|--------|------|--------|
| 7.1 | 文脈分析レイヤー実装 | 4-6h | Phase 1-6 |
| 7.2 | マルチドメイン知識管理実装 | 5-7h | 7.1 |
| 7.3 | 知識統合・推論エンジン実装 | 6-8h | 7.1, 7.2 |
| 7.4 | テスト・検証 | 3-4h | 7.1-7.3 |
| 7.5 | ドキュメント・統合 | 2-3h | 7.1-7.4 |

**推定総時間**: 20-28 時間

---

## ✅ 成功基準

- ✅ 5+ ドメイン実装
- ✅ 隠れた意図検出精度 70%+
- ✅ クロスドメイン知識検索動作
- ✅ テスト合格率 90%+
- ✅ 因果関係推論の実装
- ✅ 不確実性管理の組み込み

---

## 📝 参考資料

- **AUTONOMOUS_LLM_BLUEPRINT.md** - 全体構想書
- **PHASE1-5_IMPLEMENTATION_REPORT.md** - Phase 1-5 実装詳細
- **PHASE6_IMPLEMENTATION_REPORT.md** - Phase 6 実装詳細
