"""メトリクス監視・ダッシュボードモジュール

フィードバックと訓練の進捗を可視化し、改善傾向を追跡します。
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from .config import get_config

logger = logging.getLogger(__name__)


@dataclass
class MetricSnapshot:
    """メトリクススナップショット"""
    timestamp: str
    feedback_count: int
    average_rating: float
    training_steps: int
    model_loss: float
    improvement_percentage: float
    response_quality_trend: str  # "improving", "stable", "declining"


class MetricTracker:
    """メトリクス監視・可視化"""
    
    def __init__(self, storage_dir: str = None, config=None):
        """
        Args:
            storage_dir: メトリクス保存先
            config: MetricsConfig オブジェクト
        """
        if config is None:
            config = get_config("metrics")
        
        self.config = config
        
        if storage_dir is None:
            storage_dir = Path(config.storage_dir)
        else:
            storage_dir = Path(storage_dir)
        
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_file = self.storage_dir / "metrics_history.jsonl"
        self.dashboard_file = self.storage_dir / "dashboard.json"
        
        # アーカイブディレクトリ初期化
        self.archive_dir = Path(config.archive_dir)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        
        self.snapshots: List[MetricSnapshot] = []
        self._load_snapshots()
        
        # アーカイブを自動実行
        if config.archive_enabled:
            self._auto_archive()
    
    def _load_snapshots(self):
        """既存のメトリクススナップショットを読み込む"""
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            snapshot = MetricSnapshot(**data)
                            self.snapshots.append(snapshot)
                logger.info(f"Loaded {len(self.snapshots)} metric snapshots")
            except Exception as e:
                logger.error(f"Failed to load snapshots: {e}")
    
    def record_snapshot(
        self,
        feedback_count: int,
        average_rating: float,
        training_steps: int,
        model_loss: float,
        improvement_percentage: float,
    ) -> MetricSnapshot:
        """
        メトリクスのスナップショットを記録
        
        Args:
            feedback_count: フィードバック総数
            average_rating: 平均評価
            training_steps: 訓練ステップ数
            model_loss: モデル損失
            improvement_percentage: 改善パーセンテージ
        
        Returns:
            記録されたMetricSnapshot
        """
        # 改善傾向を判定
        trend = self._calculate_trend(average_rating)
        
        snapshot = MetricSnapshot(
            timestamp=datetime.now().isoformat(),
            feedback_count=feedback_count,
            average_rating=average_rating,
            training_steps=training_steps,
            model_loss=model_loss,
            improvement_percentage=improvement_percentage,
            response_quality_trend=trend,
        )
        
        self.snapshots.append(snapshot)
        
        # 保存
        try:
            with open(self.metrics_file, 'a', encoding='utf-8') as f:
                data = {
                    "timestamp": snapshot.timestamp,
                    "feedback_count": snapshot.feedback_count,
                    "average_rating": snapshot.average_rating,
                    "training_steps": snapshot.training_steps,
                    "model_loss": snapshot.model_loss,
                    "improvement_percentage": snapshot.improvement_percentage,
                    "response_quality_trend": snapshot.response_quality_trend,
                }
                f.write(json.dumps(data) + '\n')
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
        
        return snapshot
    
    def _calculate_trend(self, current_rating: float) -> str:
        """
        改善傾向を計算
        
        Returns:
            "improving", "stable", "declining"
        """
        if len(self.snapshots) < 2:
            return "stable"
        
        recent = self.snapshots[-5:]  # 最近5個のスナップショット
        ratings = [s.average_rating for s in recent]
        
        # 傾向を計算
        if len(ratings) >= 3:
            recent_avg = sum(ratings[-3:]) / 3
            older_ratings = ratings[:-3]
            if older_ratings:  # 除算ゼロ対策
                older_avg = sum(older_ratings) / len(older_ratings)
                improvement_rate = (recent_avg - older_avg) / max(0.01, older_avg)
                
                if improvement_rate > 0.05:  # 5%以上の改善
                    return "improving"
                elif improvement_rate < -0.05:  # 5%以上の低下
                    return "declining"
        
        return "stable"
    
    def get_dashboard(self) -> Dict[str, Any]:
        """
        ダッシュボード用データを取得
        
        Returns:
            ダッシュボード表示用データ
        """
        if not self.snapshots:
            return self._default_dashboard()
        
        latest = self.snapshots[-1]
        
        # 時系列データを計算
        timestamps = [s.timestamp for s in self.snapshots[-24:]]  # 最大24個
        ratings = [s.average_rating for s in self.snapshots[-24:]]
        losses = [s.model_loss for s in self.snapshots[-24:]]
        improvements = [s.improvement_percentage for s in self.snapshots[-24:]]
        
        # 統計情報
        avg_rating = sum(ratings) / len(ratings) if ratings else 0.0
        max_rating = max(ratings) if ratings else 0.0
        min_rating = min(ratings) if ratings else 0.0
        
        # トレンド分析
        if len(ratings) >= 2:
            rating_improvement = ((ratings[-1] - ratings[0]) / max(0.01, ratings[0])) * 100
        else:
            rating_improvement = 0.0
        
        dashboard = {
            "timestamp": latest.timestamp,
            "current": {
                "average_rating": latest.average_rating,
                "feedback_count": latest.feedback_count,
                "training_steps": latest.training_steps,
                "model_loss": latest.model_loss,
                "response_quality_trend": latest.response_quality_trend,
            },
            "statistics": {
                "average_rating": avg_rating,
                "max_rating": max_rating,
                "min_rating": min_rating,
                "rating_improvement_percent": rating_improvement,
                "total_snapshots": len(self.snapshots),
            },
            "timeseries": {
                "timestamps": timestamps,
                "ratings": ratings,
                "losses": losses,
                "improvements": improvements,
            },
            "recommendations": self._generate_recommendations(latest),
        }
        
        # ダッシュボードを保存
        try:
            with open(self.dashboard_file, 'w', encoding='utf-8') as f:
                json.dump(dashboard, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save dashboard: {e}")
        
        return dashboard
    
    def _default_dashboard(self) -> Dict[str, Any]:
        """デフォルトダッシュボード"""
        return {
            "timestamp": datetime.now().isoformat(),
            "current": {
                "average_rating": 0.0,
                "feedback_count": 0,
                "training_steps": 0,
                "model_loss": 0.0,
                "response_quality_trend": "stable",
            },
            "statistics": {
                "average_rating": 0.0,
                "max_rating": 0.0,
                "min_rating": 0.0,
                "rating_improvement_percent": 0.0,
                "total_snapshots": 0,
            },
            "timeseries": {
                "timestamps": [],
                "ratings": [],
                "losses": [],
                "improvements": [],
            },
            "recommendations": ["データを収集してください"],
        }
    
    def _generate_recommendations(self, latest: MetricSnapshot) -> List[str]:
        """
        改善提案を生成
        
        Args:
            latest: 最新のメトリクススナップショット
        
        Returns:
            推奨アクションのリスト
        """
        recommendations = []
        
        # 評価スコアに基づく推奨
        if latest.average_rating < 0.5:
            recommendations.append("⚠️ 品質スコアが低いです。プロンプトの最適化を検討してください。")
        elif latest.average_rating < 0.7:
            recommendations.append("📊 スコアを改善する余地があります。フィードバックを分析してください。")
        else:
            recommendations.append("✅ 品質スコアは良好です。現在のプロンプトは効果的です。")
        
        # 訓練状況に基づく推奨
        if latest.feedback_count < 20:
            recommendations.append("📝 もっとフィードバックを収集して、訓練データを増やしてください。")
        elif latest.feedback_count >= 50 and latest.training_steps == 0:
            recommendations.append("🤖 十分なフィードバックがあります。マイクロファインチューニングを実行してください。")
        
        # 改善傾向に基づく推奨
        if latest.response_quality_trend == "declining":
            recommendations.append("⬇️ 品質が低下しています。モデルの設定を確認してください。")
        elif latest.response_quality_trend == "improving":
            recommendations.append("⬆️ 品質が改善されています。このままのアプローチを続けてください。")
        
        # 損失に基づく推奨
        if latest.model_loss > 0.5:
            recommendations.append("📉 モデル損失が高いです。より多くのサンプルで訓練してください。")
        
        return recommendations
    
    def get_improvement_timeline(self, hours: int = 24) -> Dict[str, Any]:
        """
        指定時間内の改善がタイムラインを取得
        
        Args:
            hours: 時間
        
        Returns:
            改善内容のタイムライン
        """
        cutoff_time = datetime.fromisoformat(datetime.now().isoformat()) - timedelta(hours=hours)
        
        recent_snapshots = [
            s for s in self.snapshots
            if datetime.fromisoformat(s.timestamp) >= cutoff_time
        ]
        
        if not recent_snapshots:
            return {
                "period_hours": hours,
                "snapshots_count": 0,
                "timeline": [],
            }
        
        timeline = []
        for i, snapshot in enumerate(recent_snapshots):
            if i > 0:
                prev = recent_snapshots[i - 1]
                rating_change = snapshot.average_rating - prev.average_rating
                loss_change = snapshot.model_loss - prev.model_loss
            else:
                rating_change = 0.0
                loss_change = 0.0
            
            event = {
                "timestamp": snapshot.timestamp,
                "rating": snapshot.average_rating,
                "rating_change": rating_change,
                "loss": snapshot.model_loss,
                "loss_change": loss_change,
                "trend": snapshot.response_quality_trend,
                "training_steps": snapshot.training_steps,
            }
            timeline.append(event)
        
        return {
            "period_hours": hours,
            "snapshots_count": len(recent_snapshots),
            "timeline": timeline,
        }
    
    def export_metrics(self) -> str:
        """
        メトリクスをMarkdown形式でエクスポート
        
        Returns:
            Markdown形式のレポート
        """
        if not self.snapshots:
            return "# メトリクスレポート\n\nデータがまだ収集されていません。"
        
        dashboard = self.get_dashboard()
        latest = self.snapshots[-1]
        
        report = f"""# 自立型LLM改善レポート

## 基本統計
- **総フィードバック数**: {latest.feedback_count}
- **平均評価スコア**: {latest.average_rating:.2%}
- **訓練ステップ数**: {latest.training_steps}
- **モデル損失**: {latest.model_loss:.4f}
- **品質傾向**: {latest.response_quality_trend}

## スコア推移
- **平均スコア**: {dashboard['statistics']['average_rating']:.2%}
- **最高スコア**: {dashboard['statistics']['max_rating']:.2%}
- **最低スコア**: {dashboard['statistics']['min_rating']:.2%}
- **改善率**: {dashboard['statistics']['rating_improvement_percent']:.1f}%

## 推奨アクション
{chr(10).join(f"- {rec}" for rec in dashboard['recommendations'])}

---
*生成日時: {datetime.now().isoformat()}*
"""
        
        return report
    
    # ========== アーカイブ機能 ==========
    
    def _auto_archive(self):
        """
        自動アーカイブを実行
        
        - retention_days を超えたデータをアーカイブ
        - ファイルサイズがmax_file_size_mb を超えたら分割
        """
        try:
            # ファイルサイズチェック
            if self.metrics_file.exists():
                file_size_mb = self.metrics_file.stat().st_size / (1024 * 1024)
                
                if file_size_mb > self.config.max_file_size_mb:
                    logger.warning(
                        f"Metrics file size ({file_size_mb:.1f}MB) exceeds limit. "
                        f"Running archival..."
                    )
                    self._archive_by_size()
            
            # 保持期間チェック
            if self.config.retention_days > 0:
                self._archive_by_retention()
            
            # 古いアーカイブ削除
            if self.config.auto_cleanup:
                self._cleanup_old_archives()
        
        except Exception as e:
            logger.error(f"Auto-archive failed: {e}")
    
    def _archive_by_retention(self):
        """
        保持期間を超えたデータをアーカイブ
        """
        cutoff_date = datetime.now() - timedelta(days=self.config.retention_days)
        cutoff_iso = cutoff_date.isoformat()
        
        # 古いスナップショットと新しいスナップショットを分割
        old_snapshots = [s for s in self.snapshots if s.timestamp < cutoff_iso]
        new_snapshots = [s for s in self.snapshots if s.timestamp >= cutoff_iso]
        
        if not old_snapshots:
            logger.debug("No snapshots to archive by retention")
            return
        
        # アーカイブファイル名を生成（日付ベース）
        archive_date = cutoff_date.strftime("%Y%m%d")
        archive_filename = self.archive_dir / f"metrics_archive_{archive_date}.jsonl"
        
        try:
            # 古いデータをアーカイブに書き込み
            with open(archive_filename, 'a', encoding='utf-8') as f:
                for snapshot in old_snapshots:
                    data = {
                        "timestamp": snapshot.timestamp,
                        "feedback_count": snapshot.feedback_count,
                        "average_rating": snapshot.average_rating,
                        "training_steps": snapshot.training_steps,
                        "model_loss": snapshot.model_loss,
                        "improvement_percentage": snapshot.improvement_percentage,
                        "response_quality_trend": snapshot.response_quality_trend,
                    }
                    f.write(json.dumps(data) + '\n')
            
            logger.info(
                f"Archived {len(old_snapshots)} old snapshots to {archive_filename.name}"
            )
            
            # メインファイルを新しいデータで再作成
            self._rewrite_metrics_file(new_snapshots)
            
            # メモリ内も更新
            self.snapshots = new_snapshots
        
        except Exception as e:
            logger.error(f"Failed to archive by retention: {e}")
    
    def _archive_by_size(self):
        """
        ファイルサイズが大きくなったデータをアーカイブで分割
        """
        # 日付ごとにグループ化
        dated_snapshots = {}
        for snapshot in self.snapshots:
            date = snapshot.timestamp.split('T')[0]
            if date not in dated_snapshots:
                dated_snapshots[date] = []
            dated_snapshots[date].append(snapshot)
        
        # 古い日付から7日分づつアーカイブ
        sorted_dates = sorted(dated_snapshots.keys())
        
        for date in sorted_dates[:-7]:  # 最新7日分は残す
            archive_filename = self.archive_dir / f"metrics_archive_{date}.jsonl"
            
            try:
                with open(archive_filename, 'w', encoding='utf-8') as f:
                    for snapshot in dated_snapshots[date]:
                        data = {
                            "timestamp": snapshot.timestamp,
                            "feedback_count": snapshot.feedback_count,
                            "average_rating": snapshot.average_rating,
                            "training_steps": snapshot.training_steps,
                            "model_loss": snapshot.model_loss,
                            "improvement_percentage": snapshot.improvement_percentage,
                            "response_quality_trend": snapshot.response_quality_trend,
                        }
                        f.write(json.dumps(data) + '\n')
                
                logger.info(f"Archived {len(dated_snapshots[date])} snapshots for {date}")
            
            except Exception as e:
                logger.error(f"Failed to archive by size for {date}: {e}")
        
        # メインファイルを最新7日分で再作成
        recent_snapshots = []
        for date in sorted_dates[-7:]:
            recent_snapshots.extend(dated_snapshots[date])
        
        self._rewrite_metrics_file(recent_snapshots)
        self.snapshots = recent_snapshots
    
    def _rewrite_metrics_file(self, snapshots: List[MetricSnapshot]):
        """
        メトリクスファイルを再作成
        """
        try:
            with open(self.metrics_file, 'w', encoding='utf-8') as f:
                for snapshot in snapshots:
                    data = {
                        "timestamp": snapshot.timestamp,
                        "feedback_count": snapshot.feedback_count,
                        "average_rating": snapshot.average_rating,
                        "training_steps": snapshot.training_steps,
                        "model_loss": snapshot.model_loss,
                        "improvement_percentage": snapshot.improvement_percentage,
                        "response_quality_trend": snapshot.response_quality_trend,
                    }
                    f.write(json.dumps(data) + '\n')
            
            logger.debug(f"Rewrote metrics file with {len(snapshots)} snapshots")
        
        except Exception as e:
            logger.error(f"Failed to rewrite metrics file: {e}")
    
    def _cleanup_old_archives(self):
        """
        保持期間を超えた古いアーカイブを削除
        """
        archive_retention_days = self.config.retention_days * 2  # アーカイブはさらに長く保持
        cutoff_date = datetime.now() - timedelta(days=archive_retention_days)
        
        try:
            for archive_file in self.archive_dir.glob("metrics_archive_*.jsonl"):
                try:
                    # ファイル名から日付を抽出
                    date_str = archive_file.stem.replace("metrics_archive_", "")
                    file_date = datetime.strptime(date_str, "%Y%m%d")
                    
                    if file_date < cutoff_date:
                        archive_file.unlink()
                        logger.info(f"Deleted old archive: {archive_file.name}")
                
                except ValueError:
                    logger.warning(f"Could not parse date from archive file: {archive_file.name}")
        
        except Exception as e:
            logger.error(f"Failed to cleanup old archives: {e}")
    
    def get_archive_info(self) -> Dict[str, Any]:
        """
        アーカイブ情報を取得
        
        Returns:
            アーカイブの統計情報
        """
        archive_files = list(self.archive_dir.glob("metrics_archive_*.jsonl"))
        
        total_archived_mb = sum(f.stat().st_size for f in archive_files) / (1024 * 1024)
        main_file_mb = 0.0
        if self.metrics_file.exists():
            main_file_mb = self.metrics_file.stat().st_size / (1024 * 1024)
        
        return {
            "main_file_size_mb": main_file_mb,
            "total_archived_size_mb": total_archived_mb,
            "archive_count": len(archive_files),
            "retention_days": self.config.retention_days,
            "archive_enabled": self.config.archive_enabled,
            "archives": [
                {
                    "filename": f.name,
                    "size_mb": f.stat().st_size / (1024 * 1024),
                    "created": datetime.fromtimestamp(f.stat().st_ctime).isoformat(),
                }
                for f in sorted(archive_files, reverse=True)
            ]
        }
    
    def restore_from_archive(self, archive_filename: str) -> bool:
        """
        アーカイブからデータを復元
        
        Args:
            archive_filename: アーカイブファイル名
        
        Returns:
            成功したか
        """
        archive_path = self.archive_dir / archive_filename
        
        if not archive_path.exists():
            logger.error(f"Archive file not found: {archive_filename}")
            return False
        
        try:
            print(f"Restoring from archive: {archive_filename}")
            
            # アーカイブから読み込み
            archived_snapshots = []
            with open(archive_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        snapshot = MetricSnapshot(**data)
                        archived_snapshots.append(snapshot)
            
            # 既存データと結合
            self.snapshots.extend(archived_snapshots)
            self.snapshots.sort(key=lambda s: s.timestamp)
            
            # ファイルに再書き込み
            self._rewrite_metrics_file(self.snapshots)
            
            logger.info(
                f"Restored {len(archived_snapshots)} snapshots from {archive_filename}"
            )
            return True
        
        except Exception as e:
            logger.error(f"Failed to restore from archive: {e}")
            return False
