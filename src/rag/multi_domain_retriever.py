"""
マルチドメイン対応Retriever
Phase 7統合版 - ドメイン別インデックス管理と情報検索

このRetrieverはドメイン別にFAISSインデックスを管理し、
効率的なドメイン指向検索を実現します。
"""

import faiss
import numpy as np
import json
import torch
from transformers import AutoTokenizer, AutoModel
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

# プロジェクトルートをこのファイルの2階層上として解決
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS_PATH = PROJECT_ROOT / "corpus"


@dataclass
class RetrievalResult:
    """検索結果データクラス"""
    domain: str
    query: str
    results: List[Dict[str, Any]] = field(default_factory=list)
    scores: List[float] = field(default_factory=list)
    retrieval_time: float = 0.0
    index_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'domain': self.domain,
            'query': self.query,
            'results': self.results,
            'scores': self.scores,
            'retrieval_time': self.retrieval_time,
            'index_count': self.index_count
        }


@dataclass
class MultiDomainRetrievalResult:
    """マルチドメイン検索結果"""
    primary_domain: str
    related_domains: List[str]
    primary_results: RetrievalResult
    related_results: Dict[str, RetrievalResult] = field(default_factory=dict)
    merged_results: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'primary_domain': self.primary_domain,
            'related_domains': self.related_domains,
            'primary_results': self.primary_results.to_dict(),
            'related_results': {
                domain: result.to_dict() 
                for domain, result in self.related_results.items()
            },
            'merged_results': self.merged_results,
            'timestamp': self.timestamp
        }


class DomainIndex:
    """ドメイン別インデックス管理"""
    
    def __init__(self, domain: str, index_path: Optional[Path] = None):
        self.domain = domain
        self.index_path = index_path or DEFAULT_CORPUS_PATH / f"corpus_{domain}.index"
        self.meta_path = index_path.parent / f"corpus_{domain}_meta.json" if index_path else DEFAULT_CORPUS_PATH / f"corpus_{domain}_meta.json"
        self.index = None
        self.meta = []
        self.embedding_dim = 1024
        self.load()
    
    def load(self):
        """ドメイン別インデックスをロード"""
        try:
            if self.index_path.exists():
                logger.info(f"Loading FAISS index for domain '{self.domain}' from {self.index_path}")
                self.index = faiss.read_index(str(self.index_path))
                
                if self.meta_path.exists():
                    with open(self.meta_path, "r", encoding="utf-8") as f:
                        self.meta = json.load(f)
                    logger.info(f"Loaded {len(self.meta)} metadata entries for domain '{self.domain}'")
                else:
                    self.meta = []
            else:
                logger.info(f"No index found for domain '{self.domain}'. Creating new index.")
                self.index = faiss.IndexFlatIP(self.embedding_dim)
                self.meta = []
        except Exception as e:
            logger.warning(f"Could not load index for domain '{self.domain}': {e}. Creating new.")
            self.index = faiss.IndexFlatIP(self.embedding_dim)
            self.meta = []
    
    def save(self):
        """ドメイン別インデックスを保存"""
        try:
            if self.index is not None:
                os.makedirs(self.index_path.parent, exist_ok=True)
                logger.info(f"Saving FAISS index for domain '{self.domain}' to {self.index_path}")
                faiss.write_index(self.index, str(self.index_path))
                
                with open(self.meta_path, "w", encoding="utf-8") as f:
                    json.dump(self.meta, f, ensure_ascii=False, indent=2)
                
                logger.info(f"Successfully saved index for domain '{self.domain}'")
        except Exception as e:
            logger.error(f"Failed to save index for domain '{self.domain}': {e}")
    
    def add_documents(self, embeddings: np.ndarray, metadata: List[Dict[str, Any]]):
        """ドメイン別インデックスにドキュメントを追加"""
        if len(embeddings) == 0:
            return
        
        self.index.add(embeddings)
        self.meta.extend(metadata)
        logger.info(f"Added {len(embeddings)} documents to domain '{self.domain}'")
    
    def search(self, query_embedding: np.ndarray, top_k: int = 5, filters: Optional[Dict[str, Any]] = None) -> Tuple[List[int], List[float]]:
        """ドメイン別インデックスを検索"""
        if self.index.ntotal == 0:
            return [], []
        # when filters are provided, search a larger candidate set and then apply meta filtering
        candidate_k = top_k * 5 if filters else top_k
        candidate_k = min(self.index.ntotal, max(1, int(candidate_k)))

        distances, indices = self.index.search(query_embedding.reshape(1, -1), int(candidate_k))

        if not filters:
            return indices[0].tolist()[:top_k], distances[0].tolist()[:top_k]

        # apply metadata filters
        results_idx = []
        results_dist = []

        def meta_matches(meta_entry: dict, filters: dict) -> bool:
            for k, v in filters.items():
                if k not in meta_entry:
                    return False
                mv = meta_entry.get(k)
                if isinstance(v, (list, tuple, set)):
                    if mv not in v:
                        return False
                else:
                    if mv != v:
                        return False
            return True

        for idx, dist in zip(indices[0], distances[0]):
            if idx < 0 or idx >= len(self.meta):
                continue
            if meta_matches(self.meta[idx], filters):
                results_idx.append(int(idx))
                results_dist.append(float(dist))
            if len(results_idx) >= top_k:
                break

        return results_idx, results_dist
    
    def get_size(self) -> int:
        """インデックスサイズを取得"""
        return self.index.ntotal if self.index else 0


class MultiDomainRetriever:
    """
    マルチドメイン対応Retriever
    
    ドメイン別にFAISSインデックスを管理し、
    複数ドメインからの効率的な情報検索を実現します。
    """
    
    def __init__(self, default_domains: Optional[List[str]] = None, embed_fn: Optional[Callable[[str], "np.ndarray"]]=None):
        """
        初期化
        
        Args:
            default_domains: デフォルトドメインリスト
        """
        # allow injecting a custom embed function for tests or light-weight environments
        self._embed_fn = embed_fn
        if self._embed_fn is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"MultiDomainRetriever is using device: {self.device}")
            # 埋め込みモデルをロード
            logger.info("Loading local embedding model (bge-m3, safetensors)...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                "BAAI/bge-m3",
                trust_remote_code=True,
            )
            self.model = AutoModel.from_pretrained(
                "BAAI/bge-m3",
                use_safetensors=True,
                trust_remote_code=True,
            ).to(self.device)
            logger.info("Local embedding model loaded successfully.")
            self.embedding_dim = 1024
        else:
            # when embed_fn is injected, avoid heavy model loading
            self.device = "cpu"
            logger.info("Using injected embedding function; skipping model load.")
            # assume embedding dim of injected fn is 1024 unless caller provides vectors of different size
            self.embedding_dim = 1024
        
        # ドメイン別インデックスを管理
        self.domain_indices: Dict[str, DomainIndex] = {}
        self.default_domains = default_domains or [
            "medical", "legal", "technical", "business", "general"
        ]
        
        # デフォルトドメインのインデックスを初期化
        for domain in self.default_domains:
            self.domain_indices[domain] = DomainIndex(domain)
        
        # キャッシュ（LRUキャッシュを簡易実装）
        self._query_cache: Dict[str, MultiDomainRetrievalResult] = {}
        self._cache_max_size = 1000
    
    def embed_query(self, text: str) -> np.ndarray:
        """クエリを埋め込みベクトルに変換"""
        if self._embed_fn is not None:
            v = self._embed_fn(text)
            return v.astype('float32')

        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)
        with torch.no_grad():
            outputs = self.model(**inputs)
            emb = outputs.last_hidden_state[:, 0, :]  # CLS token
            emb = torch.nn.functional.normalize(emb, p=2, dim=1)
        return emb[0].cpu().numpy().astype("float32")
    
    def embed_documents(self, texts: List[str]) -> np.ndarray:
        """ドキュメントテキストを埋め込みベクトルに変換"""
        if self._embed_fn is not None:
            embs = [self._embed_fn(t).astype('float32') for t in texts]
            return np.array(embs)

        embeddings = []
        for text in texts:
            inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512).to(self.device)
            with torch.no_grad():
                outputs = self.model(**inputs)
                emb = outputs.last_hidden_state[:, 0, :]
                emb = torch.nn.functional.normalize(emb, p=2, dim=1)
            embeddings.append(emb[0].cpu().numpy().astype("float32"))
        return np.array(embeddings)
    
    def retrieve_from_domain(
        self,
        query: str,
        domain: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> RetrievalResult:
        """
        特定ドメインから検索
        
        Args:
            query: 検索クエリ
            domain: ドメイン名
            top_k: 上位K件の取得
            
        Returns:
            RetrievalResult
        """
        start_time = datetime.now()
        
        if domain not in self.domain_indices:
            logger.warning(f"Domain '{domain}' not found. Initializing new domain.")
            self.domain_indices[domain] = DomainIndex(domain)
        
        domain_index = self.domain_indices[domain]
        
        # クエリを埋め込み
        query_embedding = self.embed_query(query)
        
        # ドメイン別インデックスを検索
        # pass filters through to DomainIndex.search if provided
        try:
            indices, scores = domain_index.search(query_embedding, top_k, filters=filters)
        except TypeError:
            # backward-compatible call if DomainIndex.search doesn't accept filters
            indices, scores = domain_index.search(query_embedding, top_k)
        
        # メタデータを取得
        results = []
        for idx, score in zip(indices, scores):
            if idx < len(domain_index.meta):
                result = dict(domain_index.meta[idx])
                result['score'] = float(score)
                results.append(result)
        
        retrieval_time = (datetime.now() - start_time).total_seconds()
        
        return RetrievalResult(
            domain=domain,
            query=query,
            results=results,
            scores=scores,
            retrieval_time=retrieval_time,
            index_count=domain_index.get_size()
        )
    
    def retrieve_from_multiple_domains(
        self,
        query: str,
        primary_domain: str,
        related_domains: Optional[List[str]] = None,
        top_k_per_domain: int = 5,
        use_cache: bool = True
    ) -> MultiDomainRetrievalResult:
        """
        マルチドメイン検索
        
        Args:
            query: 検索クエリ
            primary_domain: 主要ドメイン
            related_domains: 関連ドメインリスト
            top_k_per_domain: ドメイン別検索件数
            use_cache: キャッシュを使用するか
            
        Returns:
            MultiDomainRetrievalResult
        """
        # キャッシュキーを生成
        cache_key = f"{primary_domain}|{query}|{','.join(related_domains or [])}"
        
        if use_cache and cache_key in self._query_cache:
            logger.info(f"Cache hit for query: {query}")
            return self._query_cache[cache_key]
        
        # 主要ドメインから検索
        primary_results = self.retrieve_from_domain(query, primary_domain, top_k_per_domain)
        
        # 関連ドメインから検索
        related_results = {}
        if related_domains:
            for domain in related_domains:
                try:
                    related_results[domain] = self.retrieve_from_domain(query, domain, top_k_per_domain)
                except Exception as e:
                    logger.warning(f"Failed to retrieve from domain '{domain}': {e}")
        
        # 結果をマージ（主要ドメイン優先）
        merged_results = primary_results.results.copy()
        for domain, result in related_results.items():
            merged_results.extend([
                {**r, 'domain': domain} for r in result.results
            ])
        
        # スコアでソート
        merged_results.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        multi_domain_result = MultiDomainRetrievalResult(
            primary_domain=primary_domain,
            related_domains=related_domains or [],
            primary_results=primary_results,
            related_results=related_results,
            merged_results=merged_results
        )
        
        # キャッシュに保存（最大サイズ制限）
        if use_cache:
            if len(self._query_cache) >= self._cache_max_size:
                # 古いエントリを削除（簡易FIFO）
                self._query_cache.pop(next(iter(self._query_cache)))
            self._query_cache[cache_key] = multi_domain_result
        
        return multi_domain_result
    
    def add_documents_to_domain(
        self,
        domain: str,
        documents: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None
    ):
        """
        ドメインにドキュメントを追加
        
        Args:
            domain: ドメイン名
            documents: ドキュメントテキストリスト
            metadata: メタデータリスト
        """
        if domain not in self.domain_indices:
            self.domain_indices[domain] = DomainIndex(domain)
        
        # ドキュメントを埋め込み
        embeddings = self.embed_documents(documents)
        
        # メタデータが提供されていない場合は生成
        if metadata is None:
            metadata = [
                {"text": doc, "domain": domain, "timestamp": datetime.now().isoformat()}
                for doc in documents
            ]
        else:
            # ドメイン情報を追加
            for meta in metadata:
                meta['domain'] = domain
                if 'timestamp' not in meta:
                    meta['timestamp'] = datetime.now().isoformat()
        
        # インデックスに追加
        self.domain_indices[domain].add_documents(embeddings, metadata)
        
        # キャッシュをクリア
        self._query_cache.clear()
        logger.info(f"Cleared query cache after adding documents to '{domain}'")
    
    def save_all_indices(self):
        """すべてのドメインインデックスを保存"""
        for domain, domain_index in self.domain_indices.items():
            domain_index.save()
    
    def get_domain_stats(self) -> Dict[str, Dict[str, Any]]:
        """すべてのドメインの統計情報を取得"""
        stats = {}
        for domain, domain_index in self.domain_indices.items():
            stats[domain] = {
                'index_count': domain_index.get_size(),
                'metadata_count': len(domain_index.meta),
                'index_path': str(domain_index.index_path),
                'meta_path': str(domain_index.meta_path)
            }
        return stats
    
    def clear_cache(self):
        """キャッシュをクリア"""
        self._query_cache.clear()
        logger.info("Query cache cleared")
    
    def is_domain_available(self, domain: str) -> bool:
        """ドメインが利用可能か確認"""
        return domain in self.domain_indices and self.domain_indices[domain].get_size() > 0
