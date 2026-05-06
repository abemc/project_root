"""
Phase 7: 文脈分析レイヤー - 高度な文脈理解エンジン

マルチドメイン知識システムの文脈分析を行うコンポーネント群
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)


# ============================================================
# データクラス定義
# ============================================================

@dataclass
class QueryContext:
    """質問の文脈情報"""
    primary_intent: str                    # 主要意図
    domain: str                            # 推測ドメイン
    complexity: str                        # 複雑性（SIMPLE/MODERATE/COMPLEX）
    information_needs: Dict[str, List[str]]  # 情報需要の分解
    assumed_knowledge: List[str]           # 仮定される前知識
    temporal_context: str                  # 時間的背景
    
    def to_dict(self) -> Dict:
        return {
            'primary_intent': self.primary_intent,
            'domain': self.domain,
            'complexity': self.complexity,
            'information_needs': self.information_needs,
            'assumed_knowledge': self.assumed_knowledge,
            'temporal_context': self.temporal_context,
        }


@dataclass
class ImplicitIntent:
    """隠れた意図の検出結果"""
    explicit: str                          # 明示的な意図
    implicit_list: List[str] = field(default_factory=list)  # 隠れた意図（複数）
    confidence_scores: Dict[str, float] = field(default_factory=dict)  # 각 隠れた意図の確実度
    reasoning: str = ""                    # 推論理由


@dataclass
class UserMetaContext:
    """ユーザーメタコンテキスト - ユーザー知識状態"""
    user_id: str                           # ユーザーID
    knowledge_level: Dict[str, float] = field(default_factory=dict)  # ドメイン別知識レベル
    vocabulary_level: str = "intermediate"  # 語彙レベル
    conversation_history: List[Dict] = field(default_factory=list)   # 会話履歴
    established_facts: Dict[str, bool] = field(default_factory=dict) # 確認済み事実
    misconceptions: List[str] = field(default_factory=list)          # 検出誤解
    preferred_explanation_style: str = "balanced"  # 説明スタイル選好
    last_updated: datetime = field(default_factory=datetime.now)


# ============================================================
# ContextAnalyzer: 質問背景分析
# ============================================================

class ContextAnalyzer:
    """質問の背景・文脈を分析"""
    
    # 複雑性判定の閾値
    SIMPLE_THRESHOLD = 50
    COMPLEX_THRESHOLD = 200
    
    # ドメインキーワード
    DOMAIN_KEYWORDS = {
        'medical': ['医学', '医療', '医師', '病気', '治療', '症状', '診断', '健康', '薬'],
        'legal': ['法律', '判例', '契約', '訴訟', '弁護士', '法律違反', '権利', '義務'],
        'technical': ['プログラミング', 'コード', 'API', 'アルゴリズム', 'データ構造', '言語', 'フレームワーク'],
        'business': ['ビジネス', '経営', '戦略', 'マーケティング', '投資', '売上', '利益', 'ROI'],
        'science': ['科学', '物理', '化学', '生物', '実験', '理論', '証拠', '仮説'],
    }
    
    def __init__(self):
        logger.info("ContextAnalyzer initialized")
    
    def analyze_query(self, query: str, history: Optional[List[str]] = None) -> QueryContext:
        """質問の文脈を総合的に分析"""
        primary_intent = self._extract_primary_intent(query)
        domain = self._detect_domain(query)
        complexity = self._calculate_complexity(query)
        info_needs = self._extract_information_needs(query)
        assumed_knowledge = self._infer_assumed_knowledge(query, domain)
        temporal_context = self._detect_temporal_references(query)
        
        return QueryContext(
            primary_intent=primary_intent,
            domain=domain,
            complexity=complexity,
            information_needs=info_needs,
            assumed_knowledge=assumed_knowledge,
            temporal_context=temporal_context,
        )
    
    def _extract_primary_intent(self, query: str) -> str:
        """主要意図を抽出"""
        intent_markers = {
            'explanation': ['は何ですか', 'とは', '定義', '説明してください'],
            'comparison': ['違い', '比較', 'vs', 'vs.', '異なります'],
            'how_to': ['どうやって', 'どのようにして', 'やり方', '手順'],
            'why': ['なぜ', 'どうして', '理由', '原因'],
            'example': ['例えば', '例', 'サンプル'],
            'prediction': ['予測', '予想', 'これからどうなる', '将来'],
        }
        
        query_lower = query.lower()
        for intent, markers in intent_markers.items():
            if any(marker in query_lower for marker in markers):
                return intent
        
        return 'general_inquiry'
    
    def _detect_domain(self, query: str) -> str:
        """ドメインを検出"""
        query_lower = query.lower()
        domain_scores = {}
        
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            if score > 0:
                domain_scores[domain] = score
        
        if domain_scores:
            return max(domain_scores.items(), key=lambda x: x[1])[0]
        
        return 'general'
    
    def _calculate_complexity(self, query: str) -> str:
        """複雑性を計算"""
        # 単純な指標: 文字数、句読点数、複合語数
        length = len(query)
        punctuation_count = query.count('、') + query.count('。') + query.count('？')
        
        if length < self.SIMPLE_THRESHOLD:
            return 'SIMPLE'
        elif length < self.COMPLEX_THRESHOLD:
            return 'MODERATE'
        else:
            return 'COMPLEX'
    
    def _extract_information_needs(self, query: str) -> Dict[str, List[str]]:
        """情報需要を分解"""
        needs = {
            'definition': [],
            'examples': [],
            'comparison': [],
            'applications': [],
            'risks': [],
        }
        
        if any(w in query for w in ['とは', '定義', '意味']):
            needs['definition'].append('definition_needed')
        
        if any(w in query for w in ['例', '例えば', 'サンプル']):
            needs['examples'].append('examples_needed')
        
        if any(w in query for w in ['違い', '比較', '相違']):
            needs['comparison'].append('comparison_needed')
        
        if any(w in query for w in ['応用', '使用', '実装']):
            needs['applications'].append('applications_needed')
        
        if any(w in query for w in ['危険', 'リスク', 'デメリット']):
            needs['risks'].append('risks_needed')
        
        return {k: v for k, v in needs.items() if v}
    
    def _infer_assumed_knowledge(self, query: str, domain: str) -> List[str]:
        """仮定される前知識を推定"""
        assumed = []
        
        # ドメイン固有の前提知識
        if domain == 'medical':
            assumed.extend(['basic_anatomy', 'disease_mechanisms'])
        elif domain == 'legal':
            assumed.extend(['legal_terminology', 'court_system_basics'])
        elif domain == 'technical':
            assumed.extend(['programming_basics', 'algorithm_understanding'])
        elif domain == 'business':
            assumed.extend(['business_terminology', 'market_understanding'])
        
        return assumed
    
    def _detect_temporal_references(self, query: str) -> str:
        """時間的背景を検出"""
        temporal_keywords = {
            'past': ['過去', '前々から', '歴史的に', '昔'],
            'present': ['現在', '今は', '現代', 'いま'],
            'future': ['将来', '今後', 'これからは', '予測'],
            'ongoing': ['進行中', '続いている', '最近'],
        }
        
        query_lower = query.lower()
        for context, keywords in temporal_keywords.items():
            if any(kw in query_lower for kw in keywords):
                return context
        
        return 'unspecified'


# ============================================================
# ImplicitIntentDetector: 隠れた意図検出
# ============================================================

class ImplicitIntentDetector:
    """質問に隠れた意図を検出"""
    
    def __init__(self):
        logger.info("ImplicitIntentDetector initialized")
    
    def detect(self, query: str, explicit_intent: str) -> ImplicitIntent:
        """隠れた意図を検出"""
        implicit_list = []
        confidence_scores = {}
        
        # 各種隠れた意図を検出
        emotional_intent = self._extract_emotional_intent(query)
        if emotional_intent:
            implicit_list.append(emotional_intent)
            confidence_scores[emotional_intent] = 0.7
        
        meta_intent = self._extract_meta_intent(query)
        if meta_intent:
            implicit_list.append(meta_intent)
            confidence_scores[meta_intent] = 0.6
        
        clarification_intent = self._extract_clarification_intent(query)
        if clarification_intent:
            implicit_list.append(clarification_intent)
            confidence_scores[clarification_intent] = 0.5
        
        reasoning = f"Detected {len(implicit_list)} implicit intents from query"
        
        return ImplicitIntent(
            explicit=explicit_intent,
            implicit_list=implicit_list,
            confidence_scores=confidence_scores,
            reasoning=reasoning,
        )
    
    def _extract_emotional_intent(self, query: str) -> Optional[str]:
        """感情的意図を検出"""
        emotional_keywords = {
            'seek_reassurance': ['大丈夫', '心配', '怖い', '不安'],
            'seek_validation': ['同意', '正しい', '間違ってない'],
            'frustration': ['複雑', 'わからない', '難しい', 'イライラ'],
        }
        
        query_lower = query.lower()
        for intent, keywords in emotional_keywords.items():
            if any(kw in query_lower for kw in keywords):
                return intent
        
        return None
    
    def _extract_meta_intent(self, query: str) -> Optional[str]:
        """メタレベルの意図を検出"""
        meta_keywords = {
            'learn_methodology': ['学び方', '勉強', 'スキル習得'],
            'seek_perspective': ['見方', '観点', '視点', '考え方'],
            'explore_implications': ['影響', '利点', '欠点', '結果'],
        }
        
        query_lower = query.lower()
        for intent, keywords in meta_keywords.items():
            if any(kw in query_lower for kw in keywords):
                return intent
        
        return None
    
    def _extract_clarification_intent(self, query: str) -> Optional[str]:
        """明確化の意図を検出"""
        if '詳しく' in query or 'より詳細' in query or '具体的' in query:
            return 'seek_detailed_explanation'
        
        if '簡潔' in query or 'シンプル' in query or '要約' in query:
            return 'seek_concise_explanation'
        
        if '技術的' in query or 'より深く' in query or '理論' in query:
            return 'seek_technical_depth'
        
        return None


# ============================================================
# MetaContextTracker: ユーザーメタコンテキスト管理
# ============================================================

class MetaContextTracker:
    """ユーザーの知識状態・会話背景を追跡"""
    
    def __init__(self, user_id: str = "default_user"):
        self.user_id = user_id
        self.user_profile = UserMetaContext(user_id=user_id)
        logger.info(f"MetaContextTracker initialized for user: {user_id}")
    
    def update_user_profile(self, query: str, response: str, domain: str) -> None:
        """ユーザープロファイルを更新"""
        # 会話履歴に追加
        self.user_profile.conversation_history.append({
            'query': query,
            'response': response,
            'domain': domain,
            'timestamp': datetime.now().isoformat(),
        })
        
        # 知識レベルを更新
        self._update_knowledge_level(query, response, domain)
        
        # 語彙レベルを更新
        self._update_vocabulary_level(query)
        
        logger.info(f"User profile updated - domain: {domain}")
    
    def infer_knowledge_level(self, query: str, domain: str) -> float:
        """ドメイン別知識レベルを推定（0.0-1.0）"""
        if domain not in self.user_profile.knowledge_level:
            self.user_profile.knowledge_level[domain] = 0.5  # デフォルト
        
        # 質問の構造から推定
        if 'とは' in query or '定義' in query:
            # 基本的な説明を求めているので知識レベルが低い
            estimated = 0.3
        elif any(w in query for w in ['詳細', 'より深く', '応用']):
            # 高度な話題を求めているので知識レベルが高い
            estimated = 0.8
        else:
            estimated = 0.5
        
        # 平均化
        current = self.user_profile.knowledge_level.get(domain, 0.5)
        self.user_profile.knowledge_level[domain] = (current + estimated) / 2
        
        return self.user_profile.knowledge_level[domain]
    
    def _update_knowledge_level(self, query: str, response: str, domain: str) -> None:
        """知識レベルを更新"""
        level = self.infer_knowledge_level(query, domain)
        self.user_profile.knowledge_level[domain] = level
    
    def _update_vocabulary_level(self, query: str) -> None:
        """語彙レベルを更新"""
        # 簡易的な実装
        sentence_count = query.count('。') + query.count('？')
        word_count = len(query.split())
        
        if word_count > 50:
            self.user_profile.vocabulary_level = "advanced"
        elif word_count > 20:
            self.user_profile.vocabulary_level = "intermediate"
        else:
            self.user_profile.vocabulary_level = "beginner"
    
    def get_optimal_explanation_style(self, domain: str) -> str:
        """最適な説明スタイルを決定"""
        knowledge_level = self.user_profile.knowledge_level.get(domain, 0.5)
        
        if knowledge_level < 0.4:
            return "beginner_friendly"  # 基本から説明
        elif knowledge_level < 0.7:
            return "balanced"           # バランスの取れた説明
        else:
            return "advanced"           # 高度な説明
    
    def get_user_profile(self) -> UserMetaContext:
        """ユーザープロファイルを取得"""
        return self.user_profile
    
    def detect_misconceptions(self, query: str, response: str) -> List[str]:
        """誤解を検出"""
        misconceptions = []
        
        # 応答の中に「実は」「正確には」などの修正表現があれば誤解を検出
        correction_keywords = ['実は', '正確には', '誤解', '注意', '陥りやすい誤り']
        
        if any(kw in response for kw in correction_keywords):
            misconceptions.append('detected_in_response')
        
        self.user_profile.misconceptions.extend(misconceptions)
        return misconceptions
