"""
RAG Integrator: エピソード記憶の自動ベクトル化・インデックス化

EpisodicMemory に新しいエピソードが追加されると、
自動的に埋め込み を生成し、FAISS インデックスに追加することで、
メモリからの検索・検索精度が向上。
"""

from typing import Dict, List, Optional, Any
import logging
import json
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class RAGIntegrator:
    """エピソード記憶 と RAG インデックスの統合管理"""
    
    def __init__(
        self,
        episodic_memory,  # EpisodicMemory インスタンス
        embed_store=None,  # FAISSStore インスタンス (optional)
        embedding_model=None,  # テキスト埋め込みモデル (optional)
        auto_index: bool = True,  # エピソード追加時に自動インデックス化
    ):
        """
        初期化
        
        Args:
            episodic_memory: エピソード記憶インスタンス
            embed_store: FAISS ストア（使用可能な場合）
            embedding_model: 埋め込み生成モデル（使用可能な場合）
            auto_index: 新エピソード時に自動ベクトル化するか
        """
        self.episodic_memory = episodic_memory
        self.embed_store = embed_store
        self.embedding_model = embedding_model
        self.auto_index = auto_index
        self.integration_log_path = episodic_memory.storage_dir / 'rag_integration.log'
        self._init_integration_metadata()
    
    def _init_integration_metadata(self):
        """統合メタデータの初期化"""
        self.metadata_path = self.episodic_memory.storage_dir / 'rag_metadata.json'
        self.metadata: Dict[str, Any] = {}
        
        if self.metadata_path.exists():
            try:
                with open(self.metadata_path, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load RAG metadata: {e}")
                self.metadata = {}
        
        # デフォルト値
        self.metadata.setdefault('indexed_episodes', {})
        self.metadata.setdefault('last_sync', None)
        self.metadata.setdefault('total_vectors', 0)
    
    def integrate_episode(self, episode: Dict[str, Any]) -> str:
        """
        新しいエピソードを記憶に追加し、自動的に RAG インデックスに含める
        
        Args:
            episode: エピソード辞書
        
        Returns:
            episode_id
        """
        # Step 1: EpisodicMemory に追加
        episode_id = self.episodic_memory.store_episode(episode)
        logger.info(f"[RAG] Episode stored: {episode_id}")
        
        # Step 2: ベクトル化（auto_index が有効の場合）
        if self.auto_index and self.embedding_model and self.embed_store:
            try:
                self._vectorize_episode(episode_id, episode)
            except Exception as e:
                logger.warning(f"[RAG] Failed to vectorize episode {episode_id}: {e}")
        
        return episode_id
    
    def _vectorize_episode(self, episode_id: str, episode: Dict[str, Any]):
        """エピソードをベクトル化して FAISS に追加"""
        # エピソードからテキストを構築
        text_parts = [
            episode.get('trigger', ''),
            episode.get('query', ''),
            episode.get('action', ''),
            episode.get('result', ''),
            episode.get('resolution', ''),
        ]
        combined_text = ' '.join([p for p in text_parts if p])
        
        if not combined_text:
            logger.debug(f"[RAG] Skipping empty episode: {episode_id}")
            return
        
        # テキスト埋め込み生成
        try:
            embedding = self.embedding_model.embed(combined_text)
        except Exception as e:
            logger.error(f"[RAG] Embedding failed for {episode_id}: {e}")
            return
        
        # FAISS に追加
        try:
            metadata = {
                'episode_id': episode_id,
                'text_preview': combined_text[:200],
                'timestamp': episode.get('timestamp', datetime.now().isoformat()),
                'confidence': episode.get('confidence', 0.5),
            }
            self.embed_store.add_vector(embedding, metadata)
            
            # 統合メタデータを更新
            self.metadata['indexed_episodes'][episode_id] = {
                'timestamp': datetime.now().isoformat(),
                'text_length': len(combined_text),
                'embedding_dim': len(embedding),
            }
            self.metadata['last_sync'] = datetime.now().isoformat()
            self.metadata['total_vectors'] = len(self.metadata['indexed_episodes'])
            
            self._save_integration_metadata()
            logger.info(f"[RAG] Episode {episode_id} vectorized and indexed")
        
        except Exception as e:
            logger.error(f"[RAG] Failed to add vector to FAISS: {e}")
    
    def search_episodes_by_semantic(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        セマンティック検索でエピソードを探す（RAG ベース）
        
        Args:
            query: 検索クエリ
            top_k: 取得件数
            min_similarity: 最小類似度閾値 (0-1)
        
        Returns:
            [episode, ...] マッチしたエピソード
        """
        if not self.embedding_model or not self.embed_store:
            logger.warning("[RAG] Semantic search not available (model/store missing)")
            return []
        
        try:
            query_embedding = self.embedding_model.embed(query)
            results = self.embed_store.search(query_embedding, top_k=top_k)
            
            # 類似度でフィルタ
            filtered = [r for r in results if r.get('similarity', 0) >= min_similarity]
            
            # エピソード ID から本体を取得
            episodes = []
            for result in filtered:
                ep_id = result.get('metadata', {}).get('episode_id')
                # 簡易実装: ID が metadata['indexed_episodes'] に存在するかチェック
                if ep_id in self.metadata['indexed_episodes']:
                    ep = next((e for e in self.episodic_memory.episodes if e.get('episode_id') == ep_id), None)
                    if ep:
                        ep['similarity_score'] = result.get('similarity', 0)
                        episodes.append(ep)
            
            return episodes
        
        except Exception as e:
            logger.error(f"[RAG] Semantic search failed: {e}")
            return []
    
    def search_hybrid(
        self,
        query: str,
        keyword_weight: float = 0.3,
        semantic_weight: float = 0.7,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        ハイブリッド検索（キーワード + セマンティック）
        
        Args:
            query: 検索クエリ
            keyword_weight: キーワード検索のウェイト
            semantic_weight: セマンティック検索のウェイト
            top_k: 取得件数
        
        Returns:
            [episode, ...] マージされたエピソード
        """
        # キーワード検索
        keyword_results = self.episodic_memory.query_episodes(query, top_k=top_k)
        
        # セマンティック検索
        semantic_results = self.search_episodes_by_semantic(query, top_k=top_k)
        
        # 結果をマージ（episode_id をキーに、スコアを平均化）
        merged = {}
        
        for i, ep in enumerate(keyword_results):
            ep_id = ep.get('episode_id')
            merged[ep_id] = {
                'episode': ep,
                'score': keyword_weight * (1.0 - i / max(len(keyword_results), 1))
            }
        
        for ep in semantic_results:
            ep_id = ep.get('episode_id')
            sim_score = ep.pop('similarity_score', 0.5)
            if ep_id in merged:
                merged[ep_id]['score'] += semantic_weight * sim_score
                merged[ep_id]['score'] /= 2  # 平均
            else:
                merged[ep_id] = {
                    'episode': ep,
                    'score': semantic_weight * sim_score
                }
        
        # スコアでソート
        sorted_results = sorted(merged.items(), key=lambda x: x[1]['score'], reverse=True)
        return [item[1]['episode'] for item in sorted_results[:top_k]]
    
    def garbage_collect(
        self,
        min_confidence: float = 0.3,
        max_age_days: int = 30,
    ) -> int:
        """
        古いまたは低信頼度のエピソードを削除
        
        Args:
            min_confidence: 最小信頼度 (0-1)
            max_age_days: 最大保持日数
        
        Returns:
            削除されたエピソード数
        """
        now = datetime.now()
        deleted_count = 0
        episodes_to_keep = []
        
        for ep in self.episodic_memory.episodes:
            confidence = float(ep.get('confidence', 0.5))
            timestamp_str = ep.get('timestamp')
            
            try:
                timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else now
                age_days = (now - timestamp).days
            except Exception:
                age_days = 0
            
            # 保持判定
            if confidence >= min_confidence and age_days <= max_age_days:
                episodes_to_keep.append(ep)
            else:
                deleted_count += 1
                logger.info(f"[RAG:GC] Deleted episode {ep.get('episode_id')}: "
                           f"confidence={confidence}, age={age_days}d")
        
        # 元のリストを更新
        self.episodic_memory.episodes = episodes_to_keep
        
        # ファイルを再生成
        try:
            with open(self.episodic_memory.file_path, 'w', encoding='utf-8') as f:
                for ep in episodes_to_keep:
                    f.write(json.dumps(ep, ensure_ascii=False) + '\n')
            logger.info(f"[RAG:GC] Garbage collection complete: deleted {deleted_count} episodes")
        except Exception as e:
            logger.error(f"[RAG:GC] Failed to update episodes file: {e}")
        
        return deleted_count
    
    def sync_to_faiss(self) -> int:
        """
        全エピソードを FAISS に再同期（リビルド）
        
        Returns:
            同期したエピソード数
        """
        if not self.embedding_model or not self.embed_store:
            logger.warning("[RAG] Sync not available (model/store missing)")
            return 0
        
        logger.info("[RAG] Starting full FAISS sync...")
        synced_count = 0
        
        for ep in self.episodic_memory.episodes:
            ep_id = ep.get('episode_id')
            if ep_id not in self.metadata['indexed_episodes']:
                try:
                    self._vectorize_episode(ep_id, ep)
                    synced_count += 1
                except Exception as e:
                    logger.error(f"[RAG] Sync failed for {ep_id}: {e}")
        
        logger.info(f"[RAG] Sync complete: {synced_count} episodes synced")
        return synced_count
    
    def _save_integration_metadata(self):
        """統合メタデータをファイルに保存"""
        try:
            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[RAG] Failed to save integration metadata: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """統合の統計情報を取得"""
        return {
            'total_episodes': len(self.episodic_memory.episodes),
            'indexed_episodes': len(self.metadata.get('indexed_episodes', {})),
            'total_vectors': self.metadata.get('total_vectors', 0),
            'last_sync': self.metadata.get('last_sync'),
            'auto_indexing_enabled': self.auto_index,
        }
