"""
Phase 7 対応クエリプリプロセッサ
隠れた意図・複雑性・ドメイン推定を活用したRAG統合
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from src.self_improvement.context_analyzer import ContextAnalyzer, ImplicitIntentDetector, MetaContextTracker
from src.self_improvement.domain_knowledge import DomainKnowledgeManager, CrossDomainLinker

@dataclass
class QueryPreprocessingResult:
    """クエリ前処理結果"""
    original_query: str
    query_context: Dict[str, Any]
    implicit_intents: Dict[str, Any]
    primary_domain: str
    related_domains: List[str]
    user_profile: Optional[Dict[str, Any]]
    complexity_level: str
    required_domains: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'original_query': self.original_query,
            'query_context': self.query_context,
            'implicit_intents': self.implicit_intents,
            'primary_domain': self.primary_domain,
            'related_domains': self.related_domains,
            'user_profile': self.user_profile,
            'complexity_level': self.complexity_level,
            'required_domains': self.required_domains
        }


class Phase7QueryPreprocessor:
    """
    Phase 7対応クエリプリプロセッサ
    
    機能:
    - クエリ背景分析（背景・複雑性・ドメイン推定）
    - 隠れた意図検出
    - マルチドメイン関連性検出
    - ユーザープロファイル管理
    """
    
    def __init__(self):
        """初期化"""
        self.context_analyzer = ContextAnalyzer()
        self.intent_detector = ImplicitIntentDetector()
        self.meta_tracker = MetaContextTracker()
        self.domain_manager = DomainKnowledgeManager()
        self.cross_domain_linker = CrossDomainLinker(self.domain_manager)
        
        # ユーザープロファイルキャッシュ
        self._user_profiles: Dict[str, Dict[str, Any]] = {}
    
    def preprocess(
        self,
        query: str,
        user_id: Optional[str] = None,
        conversation_history: Optional[List[str]] = None
    ) -> QueryPreprocessingResult:
        """
        クエリの事前処理
        
        Args:
            query: ユーザークエリ
            user_id: ユーザーID（オプション）
            conversation_history: 会話履歴（オプション）
        
        Returns:
            クエリ前処理結果
        """
        
        # 1. 文脈分析
        query_context = self.context_analyzer.analyze_query(query)
        
        # 2. 隠れた意図検出（明示的意図を先に取得）
        explicit_intent = query_context.primary_intent
        implicit_intent_obj = self.intent_detector.detect(query, explicit_intent)
        implicit_intents = {
            intent: True for intent in implicit_intent_obj.implicit_list
        }
        
        # 3. 複雑性レベル判定
        complexity_level = query_context.complexity
        
        # 4. ドメイン推定 (タプルリストを処理)
        domain_result = self.domain_manager.infer_domain_from_query(query)
        if isinstance(domain_result, list) and domain_result:
            if isinstance(domain_result[0], tuple):
                primary_domain = domain_result[0][0]  # 最初のドメイン名を取得
            else:
                primary_domain = domain_result[0]
        else:
            primary_domain = domain_result if domain_result else 'general'
        
        # 5. 関連ドメイン検索
        related_domains = self._find_related_domains(
            primary_domain,
            implicit_intents
        )
        
        # 6. 必要なドメイン集計
        required_domains = [primary_domain]
        if related_domains:
            for domain in related_domains:
                if isinstance(domain, (list, tuple)):
                    domain = domain[0] if domain else 'general'
                if domain not in required_domains:
                    required_domains.append(domain)
        
        # 7. ユーザープロファイル取得（オプション）
        user_profile = None
        if user_id:
            user_profile = self._get_or_create_user_profile(
                user_id,
                conversation_history
            )
        
        return QueryPreprocessingResult(
            original_query=query,
            query_context=query_context.to_dict(),
            implicit_intents=implicit_intents,
            primary_domain=primary_domain,
            related_domains=related_domains,
            user_profile=user_profile,
            complexity_level=complexity_level,
            required_domains=required_domains
        )
    
    def _find_related_domains(
        self,
        primary_domain: str,
        implicit_intents: Dict[str, Any]
    ) -> List[str]:
        """
        関連ドメインを特定
        
        Args:
            primary_domain: 主要ドメイン
            implicit_intents: 隠れた意図
        
        Returns:
            関連ドメインリスト
        """
        related_domains = []
        
        # 1. CrossDomainLinkerから関連ドメインを取得
        try:
            linked_domains = self.cross_domain_linker.find_related_domains(primary_domain)
            # CrossDomainLink オブジェクトからターゲットドメイン名を抽出
            for link in linked_domains:
                if hasattr(link, 'target_domain'):
                    related_domains.append(link.target_domain)
                elif isinstance(link, str):
                    related_domains.append(link)
        except Exception:
            pass
        
        # 2. 隠れた意図に基づく追加ドメイン推定
        # 例: 法律相談 → 法律 + ビジネス ドメイン
        intent_domain_map = {
            'seek_advice': ['medical', 'legal', 'business'],
            'learn_methodology': ['technical', 'science'],
            'explore_implications': ['business', 'legal', 'science'],
            'solve_problem': ['technical', 'science'],
        }
        
        for intent_type, domains in intent_domain_map.items():
            if intent_type in implicit_intents and implicit_intents[intent_type]:
                related_domains.extend(domains)
        
        # 重複削除
        related_domains_set = set()
        for domain in related_domains:
            if isinstance(domain, str):
                related_domains_set.add(domain)
        related_domains = list(related_domains_set)
        
        # 主要ドメインはリストから削除
        if primary_domain in related_domains:
            related_domains.remove(primary_domain)
        
        return related_domains
    
    def _get_or_create_user_profile(
        self,
        user_id: str,
        conversation_history: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        ユーザープロファイルを取得または作成
        
        Args:
            user_id: ユーザーID
            conversation_history: 会話履歴
        
        Returns:
            ユーザープロファイル
        """
        # キャッシュから取得
        if user_id in self._user_profiles:
            profile = self._user_profiles[user_id]
        else:
            # 新規作成
            profile = self.meta_tracker.create_user_profile(user_id)
            self._user_profiles[user_id] = profile
        
        # 会話履歴から更新
        if conversation_history:
            self.meta_tracker.update_profile_from_history(
                profile,
                conversation_history
            )
        
        return profile
    
    def update_user_profile(
        self,
        user_id: str,
        query: str,
        response: str
    ) -> None:
        """
        クエリと応答からユーザープロファイルを更新
        
        Args:
            user_id: ユーザーID
            query: ユーザークエリ
            response: システム応答
        """
        if user_id not in self._user_profiles:
            self._user_profiles[user_id] = self.meta_tracker.create_user_profile(user_id)
        
        profile = self._user_profiles[user_id]
        self.meta_tracker.update_profile_with_interaction(
            profile,
            query,
            response
        )
    
    def get_context_adapted_prompt(
        self,
        preprocessing_result: QueryPreprocessingResult,
        base_prompt: str
    ) -> str:
        """
        文脈適応的なプロンプトを生成
        
        Args:
            preprocessing_result: クエリ前処理結果
            base_prompt: ベースプロンプト
        
        Returns:
            適応されたプロンプト
        """
        adapted_prompt = base_prompt
        
        # 1. 複雑性レベルに応じた指示追加
        if preprocessing_result.complexity_level == 'SIMPLE':
            adapted_prompt += "\n簡潔でわかりやすい説明をしてください。"
        elif preprocessing_result.complexity_level == 'COMPLEX':
            adapted_prompt += "\n詳細で技術的な説明をしてください。不確実性も明示してください。"
        
        # 2. マルチドメイン指示
        if len(preprocessing_result.required_domains) > 1:
            domains_str = "、".join(preprocessing_result.required_domains)
            adapted_prompt += f"\n以下の複数分野から統合的に回答してください: {domains_str}"
        
        # 3. 隠れた意図に基づくカスタマイズ
        if 'seek_reassurance' in preprocessing_result.implicit_intents:
            adapted_prompt += "\n不安解消に配慮した前向きな回答をしてください。"
        
        if 'learn_methodology' in preprocessing_result.implicit_intents:
            adapted_prompt += "\n方法論や背景理由を詳しく説明してください。"
        
        # 4. ユーザー知識レベルに応じた調整
        if preprocessing_result.user_profile:
            knowledge_level = preprocessing_result.user_profile.get('knowledge_level', 'intermediate')
            if knowledge_level == 'beginner':
                adapted_prompt += "\n基本から説明し、専門用語は避けてください。"
            elif knowledge_level == 'advanced':
                adapted_prompt += "\n専門的な背景知識を前提にしても構いません。"
        
        return adapted_prompt


class MultiDomainRetriever:
    """
    マルチドメイン対応レトリーバー
    複数ドメインから統合的に知識を検索
    """
    
    def __init__(self, base_retriever):
        """
        初期化
        
        Args:
            base_retriever: ベースRetrieverインスタンス
        """
        self.base_retriever = base_retriever
        self.query_preprocessor = Phase7QueryPreprocessor()
        self.domain_manager = DomainKnowledgeManager()
    
    def retrieve_multi_domain(
        self,
        query: str,
        top_k: int = 5,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        複数ドメインから統合的に検索
        
        Args:
            query: クエリ
            top_k: 取得する上位результ数
            user_id: ユーザーID（オプション）
        
        Returns:
            {
                'preprocessing': QueryPreprocessingResult,
                'results_by_domain': {domain: [documents]},
                'merged_results': [documents]
            }
        """
        
        # 1. クエリ前処理
        preprocessing = self.query_preprocessor.preprocess(
            query,
            user_id=user_id
        )
        
        # 2. ドメイン別に検索
        results_by_domain = {}
        all_results = []
        
        for domain in preprocessing.required_domains:
            try:
                # ドメイン固有のメタデータフィルタ付きで検索
                domain_results = self.base_retriever.retrieve(
                    query,
                    top_k=top_k,
                    domain_filter=domain
                )
                results_by_domain[domain] = domain_results
                all_results.extend(domain_results)
            except Exception as e:
                print(f"⚠️ ドメイン '{domain}' 検索エラー: {e}")
        
        # 3. スコアリングとマージ
        merged_results = self._merge_and_rerank(all_results, top_k)
        
        return {
            'preprocessing': preprocessing,
            'results_by_domain': results_by_domain,
            'merged_results': merged_results
        }
    
    def _merge_and_rerank(self, results: List[Any], top_k: int) -> List[Any]:
        """
        複数ドメインの結果をマージしてリランキング
        
        Args:
            results: すべての検索結果
            top_k: 返す結果数
        
        Returns:
            リランキング済み結果
        """
        if not results:
            return []
        
        # スコアでソート
        sorted_results = sorted(
            results,
            key=lambda x: getattr(x, 'score', 0.0),
            reverse=True
        )
        
        return sorted_results[:top_k]
