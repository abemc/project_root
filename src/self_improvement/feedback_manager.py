"""フィードバック管理モジュール

ユーザーのフィードバックを記録、分析、分類し、モデルの改善に活用します。
"""

import json
import logging
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Feedback:
    """単一のフィードバック"""
    id: str
    timestamp: str
    user_query: str
    model_response: str
    rating: float  # 0.0-1.0
    feedback_text: Optional[str] = None
    tags: List[str] = None
    suggestions: Optional[str] = None
    response_id: Optional[str] = None
    query_hash: Optional[str] = None
    model_name: Optional[str] = None
    prompt_version: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict:
        return asdict(self)


class FeedbackManager:
    """フィードバックの記録と分析"""
    
    def __init__(self, storage_dir: str = None):
        """
        Args:
            storage_dir: フィードバック保存先。デフォルトはlogs/feedback
        """
        if storage_dir is None:
            storage_dir = Path("logs/feedback")
        
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.feedback_file = self.storage_dir / "feedback_history.jsonl"
        self.summary_file = self.storage_dir / "feedback_summary.json"
        
        # メモリキャッシュ
        self.feedback_cache: List[Feedback] = []
        self._load_cache()
    
    def _load_cache(self):
        """既存のフィードバックをメモリに読み込む"""
        if self.feedback_file.exists():
            try:
                with open(self.feedback_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            feedback = Feedback(**data)
                            self.feedback_cache.append(feedback)
                logger.info(f"Loaded {len(self.feedback_cache)} feedback records")
            except Exception as e:
                logger.error(f"Failed to load feedback cache: {e}")
    
    def record_feedback(
        self,
        user_query: str,
        model_response: str,
        rating: float,
        feedback_text: Optional[str] = None,
        tags: Optional[List[str]] = None,
        suggestions: Optional[str] = None,
        response_id: Optional[str] = None,
        query_hash: Optional[str] = None,
        model_name: Optional[str] = None,
        prompt_version: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Feedback:
        """
        フィードバックを記録
        
        Args:
            user_query: ユーザーの入力
            model_response: モデルの出力
            rating: 評価（0.0-1.0）
            feedback_text: フィードバックテキスト
            tags: タグ（良い点、改善点など）
            suggestions: 改善提案
        
        Returns:
            記録されたFeedbackオブジェクト
        """
        # 一意なIDを生成
        feedback_id = hashlib.md5(
            f"{user_query}{model_response}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:8]
        
        feedback = Feedback(
            id=feedback_id,
            timestamp=datetime.now().isoformat(),
            user_query=user_query,
            model_response=model_response,
            rating=max(0.0, min(1.0, rating)),  # クリップ
            feedback_text=feedback_text,
            tags=tags or [],
            suggestions=suggestions,
            response_id=response_id,
            query_hash=query_hash or hashlib.sha256((user_query or "").encode("utf-8", errors="ignore")).hexdigest()[:16],
            model_name=model_name,
            prompt_version=prompt_version,
            metadata=metadata or {},
        )
        
        self.feedback_cache.append(feedback)
        
        # ディスクに追記
        try:
            with open(self.feedback_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(feedback.to_dict()) + '\n')
            logger.info(f"Recorded feedback: {feedback_id} (rating: {rating})")
        except Exception as e:
            logger.error(f"Failed to record feedback: {e}")
        
        return feedback
    
    def get_recent_feedback(self, n: int = 50) -> List[Feedback]:
        """最近のフィードバック取得"""
        return self.feedback_cache[-n:]
    
    def get_feedback_by_rating(self, min_rating: float = None, max_rating: float = None) -> List[Feedback]:
        """評価でフィルタ"""
        feedback = self.feedback_cache
        
        if min_rating is not None:
            feedback = [f for f in feedback if f.rating >= min_rating]
        if max_rating is not None:
            feedback = [f for f in feedback if f.rating <= max_rating]
        
        return feedback
    
    def get_feedback_by_tags(self, tags: List[str]) -> List[Feedback]:
        """タグでフィルタ"""
        return [f for f in self.feedback_cache if any(tag in f.tags for tag in tags)]
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """フィードバック統計"""
        if not self.feedback_cache:
            return {
                "total_count": 0,
                "average_rating": 0.0,
                "rating_distribution": {},
                "top_issues": [],
                "top_improvements": [],
            }
        
        ratings = [f.rating for f in self.feedback_cache]
        
        # タグの集計
        tag_counts = {}
        for feedback in self.feedback_cache:
            for tag in feedback.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        summary = {
            "total_count": len(self.feedback_cache),
            "average_rating": float(np.mean(ratings)),
            "median_rating": float(np.median(ratings)),
            "std_rating": float(np.std(ratings)),
            "min_rating": float(np.min(ratings)),
            "max_rating": float(np.max(ratings)),
            "rating_distribution": {
                "0-20%": len([r for r in ratings if r < 0.2]),
                "20-40%": len([r for r in ratings if 0.2 <= r < 0.4]),
                "40-60%": len([r for r in ratings if 0.4 <= r < 0.6]),
                "60-80%": len([r for r in ratings if 0.6 <= r < 0.8]),
                "80-100%": len([r for r in ratings if r >= 0.8]),
            },
            "top_tags": sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10],
        }
        
        # サマリーを保存
        try:
            with open(self.summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save summary: {e}")
        
        return summary
    
    def export_for_training(self, min_rating: float = 0.7) -> List[Dict[str, Any]]:
        """
        訓練用データとしてエクスポート
        
        Args:
            min_rating: 含める最小評価
        
        Returns:
            訓練用サンプルリスト
        """
        training_data = []
        good_feedback = self.get_feedback_by_rating(min_rating=min_rating)
        
        for feedback in good_feedback:
            training_data.append({
                "instruction": feedback.user_query,
                "output": feedback.model_response,
                "rating": feedback.rating,
                "feedback": feedback.feedback_text,
                "tags": feedback.tags,
                "response_id": feedback.response_id,
                "query_hash": feedback.query_hash,
                "model_name": feedback.model_name,
                "prompt_version": feedback.prompt_version,
                "metadata": feedback.metadata,
            })
        
        return training_data
    
    def get_improvement_areas(self, percentile: float = 25) -> List[str]:
        """
        改善が必要な領域を特定
        
        Args:
            percentile: この下位パーセンタイル以下のフィードバックを分析
        
        Returns:
            改善領域のリスト
        """
        ratings = [f.rating for f in self.feedback_cache]
        if not ratings:
            return []
        
        threshold = np.percentile(ratings, percentile)
        poor_feedback = [f for f in self.feedback_cache if f.rating <= threshold]
        
        # タグを集計
        issue_tags = {}
        for feedback in poor_feedback:
            for tag in feedback.tags:
                if "問題" in tag or "改善" in tag.lower() or "エラー" in tag:
                    issue_tags[tag] = issue_tags.get(tag, 0) + 1
        
        # 頻度順にソート
        return [tag for tag, _ in sorted(issue_tags.items(), key=lambda x: x[1], reverse=True)]
    
    def get_stats_by_time_window(self, hours: int = 24) -> Dict[str, Any]:
        """指定時間内のフィードバック統計"""
        from datetime import timedelta
        
        cutoff_time = datetime.fromisoformat(datetime.now().isoformat()) - timedelta(hours=hours)
        recent_feedback = [
            f for f in self.feedback_cache
            if datetime.fromisoformat(f.timestamp) >= cutoff_time
        ]
        
        if not recent_feedback:
            return {"count": 0, "average_rating": 0.0}
        
        ratings = [f.rating for f in recent_feedback]
        return {
            "count": len(recent_feedback),
            "average_rating": float(np.mean(ratings)),
            "improvement": len([f for f in recent_feedback if f.rating >= 0.7]) / len(recent_feedback),
        }
