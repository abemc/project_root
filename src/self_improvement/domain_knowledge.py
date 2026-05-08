"""
Phase 7: マルチドメイン知識管理レイヤー

複数分野の知識を体系的に管理・検索するコンポーネント群
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


# ============================================================
# データクラス定義
# ============================================================

@dataclass
class Domain:
    """ドメイン定義"""
    name: str                              # ドメイン名（medical, legal等）
    description: str                       # 説明
    key_concepts: List[str] = field(default_factory=list)  # 主要概念
    prerequisites: List[str] = field(default_factory=list)  # 前提知識
    related_domains: List[str] = field(default_factory=list)  # 関連ドメイン
    update_frequency: str = "weekly"       # 更新頻度
    last_updated: datetime = field(default_factory=datetime.now)  # 最終更新
    quality_score: float = 0.8             # 知識品質スコア

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'description': self.description,
            'key_concepts': self.key_concepts,
            'prerequisites': self.prerequisites,
            'related_domains': self.related_domains,
            'update_frequency': self.update_frequency,
            'last_updated': self.last_updated.isoformat(),
            'quality_score': self.quality_score,
        }


@dataclass
class CrossDomainLink:
    """ドメイン間リンク"""
    source_domain: str                     # ソースドメイン
    target_domain: str                     # ターゲットドメイン
    relation_type: str                     # 関連タイプ
    bridge_concepts: List[str] = field(default_factory=list)  # 架け橋概念
    strength: float = 0.7                  # 関連の強さ(0-1)
    description: str = ""                  # 説明


@dataclass
class KnowledgeItem:
    """知識アイテム"""
    id: str                                # ID
    domain: str                            # ドメイン
    concept: str                           # 概念
    content: str                           # 内容
    confidence: float = 0.8                # 信頼度
    sources: List[str] = field(default_factory=list)  # 知識源
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


# ============================================================
# DomainKnowledgeManager: ドメイン知識管理
# ============================================================

class DomainKnowledgeManager:
    """複数ドメインの知識を登録・管理"""
    
    # デフォルトドメイン定義
    DEFAULT_DOMAINS = [
        Domain(
            name='medical',
            description='医学・医療知識',
            key_concepts=['diagnosis', 'treatment', 'symptoms', 'anatomy', '医学', '医療', '診断', '治療', '症状', '病気', 'COVID', 'ワクチン', 'patient', 'disease', 'health', 'clinic', 'hospital', '薬', 'medicine', '患者', 'doctor'],
            related_domains=['biology', 'chemistry'],
        ),
        Domain(
            name='legal',
            description='法律・法学知識',
            key_concepts=['contract', 'liability', 'rights', 'procedures', '法律', '法的', '法', '契約', '規制', 'law', 'legal', 'court', 'judge', '裁判', '訴訟', '権利', 'legislation', '条項', '規程', 'regulation', '知的財産権', 'intellectual', 'property', 'patent', '特許', 'copyright', '著作権', 'trademark', 'IP', '法的リスク', 'liability', 'compliance', '遵守', 'international', '国際法'],
            related_domains=['business', 'ethics'],
        ),
        Domain(
            name='technical',
            description='技術・プログラミング知識',
            key_concepts=['algorithms', 'data_structures', 'design_patterns', '技術', 'プログラミング', 'コード', 'コンピュータ', 'computer', 'programming', 'code', 'software', 'API', 'database', 'algorithm', '最適化', 'optimization', 'system', 'developer', 'python', 'javascript', 'java', 'golang', 'アルゴリズム', 'クラウド', 'マイクロサービス', 'インデックス', 'セキュリティ', 'アーキテクチャ', 'デザインパターン', 'スケーラビリティ', 'legacy', 'レガシー', 'migration', '移行', 'pipeline', 'パイプライン', 'ci/cd', 'devops', 'デプロイメント', 'deployment', 'インフラストラクチャ', 'infrastructure', 'docker', 'kubernetes', 'container', 'monitoring', '監視', 'logging', 'ログ', 'resilience', 'レジリエンス', 'scalability', 'スケーラビリティ', 'performance', 'パフォーマンス', 'testing', 'テスト', 'automation', '自動化'],
            related_domains=['mathematics', 'business'],
        ),
        Domain(
            name='business',
            description='ビジネス・経営知識',
            key_concepts=['strategy', 'marketing', 'finance', 'operations', 'business', 'ビジネス', '経営', 'management', '戦略', '市場', 'market', 'sales', '営業', '企業', 'company', 'business_model', '経営戦略', 'ROI', 'profit', '利益', '投資', 'investment', 'entrepreneur', 'デジタルトランスフォーメーション', 'DX', '業務改革', 'transformation', 'organizational', 'change', 'スティナビリティ', 'sustainability', 'サステナビリティ', '業界動向', '新市場', 'expansion', '経営判断', 'decision', '組織変革', '実装戦略'],
            related_domains=['technical', 'legal', 'psychology'],
        ),
        Domain(
            name='science',
            description='自然科学知識',
            key_concepts=['physics', 'chemistry', 'biology', 'experiments', '科学', '自然科学', '物理', '化学', '生物', 'experiment', 'research', '研究', 'theory', '理論', 'energy', 'atom', '原子', 'element', 'molecule', '分子', 'reaction', 'データサイエンス', 'data science', '統計', 'statistics', 'statistical', '数学', 'mathematics', 'モデル', 'model', '分析', 'analytical', '定量', 'quantitative', '定性', 'qualitative', '仮説', 'hypothesis', '検証', 'validation', 'エネルギー', 'environmental', '環境', 'ecology', 'エコロジー', 'sustainability', 'サステナビリティ', '気候', 'climate', '生態系', 'ecosystem', '遺伝', 'genetic', 'dna', 'メタボーム', 'metabolomics', 'lifespan'],
            related_domains=['mathematics', 'technical'],
        ),
    ]
    
    def __init__(self):
        self.domains: Dict[str, Domain] = {}
        self.knowledge_items: Dict[str, Dict[str, KnowledgeItem]] = {}  # domain -> id -> item
        
        # デフォルトドメインを初期化
        for domain in self.DEFAULT_DOMAINS:
            self.register_domain(domain)
        
        logger.info(f"DomainKnowledgeManager initialized with {len(self.domains)} domains")
    
    def register_domain(self, domain: Domain) -> None:
        """ドメインを登録"""
        self.domains[domain.name] = domain
        self.knowledge_items[domain.name] = {}
        logger.info(f"Domain registered: {domain.name}")
    
    def list_domains(self) -> List[Domain]:
        """登録済みドメイン一覧を取得"""
        return list(self.domains.values())
    
    def get_domain(self, domain_name: str) -> Optional[Domain]:
        """ドメインを取得"""
        return self.domains.get(domain_name)
    
    def update_domain(self, domain: Domain) -> None:
        """ドメインを更新"""
        if domain.name in self.domains:
            domain.last_updated = datetime.now()
            self.domains[domain.name] = domain
            logger.info(f"Domain updated: {domain.name}")
    
    def infer_domain_from_query(self, query: str) -> List[Tuple[str, float]]:
        """
        クエリからドメインを推定（改善版v4 - IPキーワード直接検出）
        
        改善点:
        1. 複合キーワード検出（直接文字列検索）
        2. IP関連キーワードの優先検出
        3. Crossover ケースの明示的ルール
        """
        import re
        
        domain_scores: Dict[str, float] = {}
        query_lower = query.lower()
        
        # クエリを単語に分割
        query_words = re.findall(r'\w+', query_lower)
        query_words_set = set(query_words)
        
        # === IP関連キーワード検出（最優先） ===
        ip_keywords = ['知的財産権', '知的財産', 'intellectual property', 'patent', '特許', 'copyright', '著作権', 'trademark', 'ip']
        has_ip_keyword = any(ip_keyword in query_lower for ip_keyword in ip_keywords)
        
        # ビジネス関連の修飾語を検出
        business_modifiers = ['ビジネス', 'business', '戦略', 'strategy', '経営', 'management']
        has_business_modifier = any(mod in query_lower for mod in business_modifiers)
        
        # === 複合キーワード検出ルール ===
        # ルール1: IP + Business修飾語 = Legal（IP側が主要）
        is_ip_business_crossover = has_ip_keyword and has_business_modifier
        
        # ルール2: 分析 + 技術 = Business（主目的）
        analysis_keywords = ['分析', 'analysis', '業界動向', 'industry', 'trend']
        tech_keywords = ['技術', 'technology', 'technical', 'トレンド']
        has_analysis = any(k in query_lower for k in analysis_keywords)
        has_tech = any(k in query_lower for k in tech_keywords)
        is_analysis_tech_crossover = has_analysis and has_tech
        
        # ルール3: 技術 + エネルギー/科学基盤 = Science（科学基盤が主要）
        # 具体的に「エネルギー」キーワードと一緒に「基盤」「基礎」がある場合のみ
        energy_keywords = ['エネルギー', 'energy']
        science_foundation_keywords = ['基盤', 'foundation', '基礎', 'basis', '科学的']
        has_energy = any(k in query_lower for k in energy_keywords)
        has_science_foundation = any(k in query_lower for k in science_foundation_keywords)
        is_tech_science_crossover = has_tech and has_energy and has_science_foundation
        
        # 強いシグナルキーワード
        legal_strong_indicators = {
            'single': {'知的財産', 'intellectual', 'property', 'patent', 'copyright', 'ip', 'trademark', '著作権', '特許'},
        }
        business_strong_indicators = {
            'single': {'分析', 'analysis', '業界動向', 'dx', 'デジタル', 'transformation'},
        }
        
        for domain_name, domain in self.domains.items():
            score = 0.0
            matched_concepts = 0
            strong_match = False
            
            # IP + Business crossover処理
            if is_ip_business_crossover and domain_name in ['legal', 'business']:
                if domain_name == 'legal':
                    # Legalに大きなボーナス
                    score += 3.0
                    strong_match = True
                elif domain_name == 'business':
                    # Businessにペナルティ
                    score -= 1.0
            
            # Analysis + Tech crossover処理
            if is_analysis_tech_crossover and domain_name in ['business', 'technical']:
                if domain_name == 'business' and has_analysis:
                    # 主要な分析目的ならBusinessに優先権
                    score += 1.5
                    strong_match = True
                elif domain_name == 'technical':
                    # Technicalへのペナルティ
                    score -= 0.5
            
            # Tech + Science crossover処理（エネルギー・科学基盤）
            if is_tech_science_crossover and domain_name in ['science', 'business', 'technical']:
                if domain_name == 'science':
                    # Scienceに大きなボーナス（科学基盤が主要）
                    score += 2.5
                    strong_match = True
                elif domain_name == 'business':
                    # Businessにペナルティ
                    score -= 1.5
                elif domain_name == 'technical':
                    # Technicalにペナルティ
                    score -= 0.5
            
            for concept in domain.key_concepts:
                concept_lower = concept.lower()
                
                # 最小文字数チェック（1-2文字はスキップ）
                if len(concept_lower) <= 1:
                    continue
                
                # 1. 完全一致（単語レベル）
                if concept_lower in query_words_set:
                    base_score = 1.0
                    # 強いシグナルキーワード確認
                    if domain_name == 'legal' and concept_lower in legal_strong_indicators['single']:
                        base_score = 1.8 if not is_ip_business_crossover else 2.5
                        strong_match = True
                    elif domain_name == 'business' and concept_lower in business_strong_indicators['single']:
                        if is_analysis_tech_crossover and concept_lower in {'分析', 'analysis', '業界動向'}:
                            base_score = 2.0
                        else:
                            base_score = 1.5
                        strong_match = True
                    score += base_score
                    matched_concepts += 1
                # 2. 部分一致（含む）
                elif concept_lower in query_lower:
                    base_score = 0.6
                    # 部分一致でも強いシグナルなら加点
                    if domain_name == 'legal' and concept_lower in legal_strong_indicators['single']:
                        base_score = 1.3
                        strong_match = True
                    elif domain_name == 'business' and concept_lower in business_strong_indicators['single']:
                        base_score = 1.1
                        strong_match = True
                    score += base_score
                    matched_concepts += 1
                # 3. 単語分割マッチ
                else:
                    concept_words = set(re.findall(r'\w+', concept_lower))
                    overlap = len(query_words_set & concept_words)
                    if overlap > 0:
                        score += overlap * 0.3
                        matched_concepts += 0.5
            
            # ドメイン名の直接マッチ（ボーナス）
            if domain_name in query_lower:
                score += 0.5
            
            # マッチしたコンセプト数による正規化
            if matched_concepts > 0:
                if matched_concepts >= 2:
                    score = score
                else:
                    if strong_match or is_ip_business_crossover:
                        # 強いシグナルはペナルティなし
                        score = score
                    else:
                        score = score * 0.85
                
                domain_scores[domain_name] = score
        
        # スコアでソート
        sorted_domains = sorted(domain_scores.items(), 
                             key=lambda x: x[1], reverse=True)
        
        # 正規化（トップスコアに基づく）
        if sorted_domains:
            max_score = sorted_domains[0][1]
            if max_score > 0:
                # スコア差が小さいものを除外（信頼度 < 0.5）
                result = []
                for d, s in sorted_domains:
                    normalized_score = min(s / max_score, 1.0)
                    if normalized_score >= 0.5 or d == sorted_domains[0][0]:
                        result.append((d, normalized_score))
                return result
        
        return [('general', 0.5)]
    
    def add_knowledge_item(self, item: KnowledgeItem) -> str:
        """知識アイテムを追加"""
        if item.domain not in self.knowledge_items:
            self.knowledge_items[item.domain] = {}
        
        self.knowledge_items[item.domain][item.id] = item
        logger.info(f"Knowledge item added: {item.id}")
        return item.id
    
    def get_knowledge_items_for_domain(self, domain: str) -> List[KnowledgeItem]:
        """ドメイン別知識アイテムを取得"""
        return list(self.knowledge_items.get(domain, {}).values())


# ============================================================
# CrossDomainLinker: ドメイン間リンク管理
# ============================================================

class CrossDomainLinker:
    """ドメイン間の関連関係を管理・検出"""
    
    def __init__(self, domain_manager: DomainKnowledgeManager):
        self.domain_manager = domain_manager
        self.links: List[CrossDomainLink] = []
        self._initialize_default_links()
        logger.info("CrossDomainLinker initialized")
    
    def _initialize_default_links(self) -> None:
        """デフォルトのドメイン間リンクを設定"""
        default_links = [
            CrossDomainLink(
                source_domain='medical',
                target_domain='biology',
                relation_type='prerequisite',
                bridge_concepts=['anatomy', 'physiology', 'cells'],
                strength=0.9,
            ),
            CrossDomainLink(
                source_domain='technical',
                target_domain='mathematics',
                relation_type='prerequisite',
                bridge_concepts=['algorithms', 'complexity', 'logic'],
                strength=0.9,
            ),
            CrossDomainLink(
                source_domain='business',
                target_domain='legal',
                relation_type='related',
                bridge_concepts=['contracts', 'regulations', 'compliance'],
                strength=0.8,
            ),
            CrossDomainLink(
                source_domain='technical',
                target_domain='business',
                relation_type='similar',
                bridge_concepts=['project_management', 'strategy', 'optimization'],
                strength=0.7,
            ),
        ]
        
        for link in default_links:
            self.links.append(link)
    
    def link_domains(self, source: str, target: str, relation_type: str,
                    bridge_concepts: List[str], strength: float = 0.7) -> CrossDomainLink:
        """ドメインをリンク"""
        link = CrossDomainLink(
            source_domain=source,
            target_domain=target,
            relation_type=relation_type,
            bridge_concepts=bridge_concepts,
            strength=strength,
        )
        
        self.links.append(link)
        logger.info(f"Domain link created: {source} -> {target}")
        return link
    
    def find_related_domains(self, domain: str, 
                            relation_type: Optional[str] = None) -> List[CrossDomainLink]:
        """関連ドメインを検索"""
        related = []
        
        for link in self.links:
            if link.source_domain == domain:
                if relation_type is None or link.relation_type == relation_type:
                    related.append(link)
        
        # 強度でソート
        related.sort(key=lambda x: x.strength, reverse=True)
        return related
    
    def infer_cross_domain_knowledge(self, query: str, primary_domain: str) -> List[str]:
        """クロスドメイン知識を推定"""
        related_domains = self.find_related_domains(primary_domain)
        cross_domain_knowledge = []
        
        for link in related_domains:
            # 該当ドメインの主要概念を追加
            target_domain = self.domain_manager.get_domain(link.target_domain)
            if target_domain:
                cross_domain_knowledge.extend(target_domain.key_concepts[:3])
        
        return cross_domain_knowledge
    
    def bridge_knowledge(self, source_domain: str, target_domain: str) -> List[str]:
        """ドメイン間の架け橋知識を取得"""
        for link in self.links:
            if (link.source_domain == source_domain and 
                link.target_domain == target_domain):
                return link.bridge_concepts
        
        return []
    
    def get_all_links(self) -> List[CrossDomainLink]:
        """すべてのリンクを取得"""
        return self.links


# ============================================================
# DomainIndexer: ドメイン内知識インデックス
# ============================================================

class DomainIndexer:
    """ドメイン内知識の効率的検索"""
    
    def __init__(self, domain_manager: DomainKnowledgeManager):
        self.domain_manager = domain_manager
        self.indices: Dict[str, Dict[str, List[str]]] = {}  # domain -> concept -> keywords
        logger.info("DomainIndexer initialized")
    
    def index_knowledge(self, domain: str, 
                       concepts: Dict[str, List[str]]) -> None:
        """知識をインデックス"""
        self.indices[domain] = concepts
        logger.info(f"Indexed knowledge for domain: {domain}")
    
    def search_in_domain(self, domain: str, query: str, top_k: int = 5) -> List[str]:
        """ドメイン内で検索"""
        if domain not in self.indices:
            # デフォルトの検索
            domain_obj = self.domain_manager.get_domain(domain)
            if domain_obj:
                return domain_obj.key_concepts[:top_k]
            return []
        
        # インデックスから検索
        query_lower = query.lower()
        results = []
        
        for concept, keywords in self.indices[domain].items():
            if any(kw.lower() in query_lower for kw in keywords):
                results.append(concept)
        
        return results[:top_k]
    
    def get_domain_hierarchy(self, domain: str) -> Dict:
        """ドメイン概念階層を取得"""
        if domain not in self.indices:
            return {}
        
        return self.indices[domain]
    
    def suggest_related_concepts(self, domain: str, concept: str) -> List[str]:
        """関連概念を提示"""
        if domain not in self.indices:
            return []
        
        concept_lower = concept.lower()
        suggestions = []
        
        for key, keywords in self.indices[domain].items():
            if concept_lower in keywords and key != concept:
                suggestions.append(key)
        
        return suggestions[:5]
    
    def build_default_indices(self) -> None:
        """デフォルトインデックスを構築"""
        # Medical domain index
        self.index_knowledge('medical', {
            'anatomy': ['body', 'organ', 'tissue', 'system'],
            'diagnosis': ['symptom', 'test', 'screening', 'examination'],
            'treatment': ['therapy', 'medication', 'surgery', 'intervention'],
        })
        
        # Technical domain index
        self.index_knowledge('technical', {
            'algorithm': ['sorting', 'searching', 'optimization', 'complexity'],
            'data_structure': ['array', 'list', 'tree', 'graph', 'hash'],
            'programming': ['code', 'language', 'framework', 'library'],
        })
        
        # Business domain index
        self.index_knowledge('business', {
            'strategy': ['planning', 'goal', 'objective', 'vision'],
            'marketing': ['audience', 'campaign', 'brand', 'promotion'],
            'finance': ['budget', 'revenue', 'investment', 'profit'],
        })
        
        logger.info("Default indices built")
