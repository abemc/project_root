"""メトリクスアーカイブ管理ユーティリティ

アーカイブの確認、復元、クリーンアップなどの管理ツールを提供します。
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List

from src.self_improvement import MetricTracker
from src.self_improvement.config import get_config


def format_size(bytes_size: float) -> str:
    """バイト数を人間が読める形式に変換"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f}{unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f}TB"


def show_archive_info(tracker: MetricTracker):
    """アーカイブ情報を表示"""
    print("\n" + "="*60)
    print("📦 メトリクスアーカイブ情報")
    print("="*60)
    
    info = tracker.get_archive_info()
    
    print(f"\n📊 ファイルサイズ:")
    print(f"   メインファイル: {info['main_file_size_mb']:.2f}MB")
    print(f"   アーカイブ合計: {info['total_archived_size_mb']:.2f}MB")
    print(f"   状態: {'有効' if info['archive_enabled'] else '無効'}")
    
    print(f"\n🗄️ アーカイブファイル ({info['archive_count']}個):")
    
    if info['archives']:
        for i, archive in enumerate(info['archives'], 1):
            print(f"   {i}. {archive['filename']}")
            print(f"      サイズ: {archive['size_mb']:.2f}MB")
            print(f"      作成日時: {archive['created']}")
    else:
        print("   アーカイブなし")
    
    print(f"\n⚙️ 設定:")
    print(f"   保持期間: {info['retention_days']}日")
    print(f"   最大ファイルサイズ: {get_config('metrics').max_file_size_mb}MB")


def show_snapshots(tracker: MetricTracker, limit: int = 10):
    """スナップショットを表示"""
    print("\n" + "="*60)
    print("📈 最近のスナップショット")
    print("="*60)
    
    if not tracker.snapshots:
        print("\nスナップショットがありません")
        return
    
    recent = tracker.snapshots[-limit:]
    
    print(f"\n最近{len(recent)}個のスナップショット:\n")
    print("時刻                       評価    フィード訓練損失  改善%   傾向")
    print("-"*70)
    
    for snapshot in recent:
        timestamp = snapshot.timestamp.split('T')[1][:8] if 'T' in snapshot.timestamp else snapshot.timestamp
        rating = f"{snapshot.average_rating:.1%}"
        fb_count = snapshot.feedback_count
        train_steps = snapshot.training_steps
        loss = f"{snapshot.model_loss:.3f}"
        improve = f"{snapshot.improvement_percentage:.1f}%"
        trend = snapshot.response_quality_trend
        
        print(f"{timestamp}  {rating:>6}  {fb_count:>3}個 {train_steps:>4}  {loss:>6} {improve:>6}  {trend}")


def cleanup_old_data(tracker: MetricTracker):
    """古いデータをクリーンアップ"""
    print("\n" + "="*60)
    print("🧹 古いアーカイブを削除")
    print("="*60)
    
    tracker._cleanup_old_archives()
    print("\n✅ クリーンアップ完了")
    
    info = tracker.get_archive_info()
    print(f"   残存アーカイブ: {info['archive_count']}個")


def restore_archive(tracker: MetricTracker, archive_name: str):
    """アーカイブから復元"""
    print("\n" + "="*60)
    print(f"🔄 アーカイブから復元: {archive_name}")
    print("="*60)
    
    success = tracker.restore_from_archive(archive_name)
    
    if success:
        print(f"\n✅ 復元成功")
        print(f"   メイン データ: {len(tracker.snapshots)}個のスナップショット")
    else:
        print(f"\n❌ 復元失敗")


def export_archive_summary(tracker: MetricTracker, output_file: str = None):
    """アーカイブサマリーをエクスポート"""
    print("\n" + "="*60)
    print("📋 アーカイブサマリーをエクスポート")
    print("="*60)
    
    info = tracker.get_archive_info()
    
    summary = {
        "export_date": datetime.now().isoformat(),
        "archive_info": {
            "main_file_size_mb": info['main_file_size_mb'],
            "total_archived_size_mb": info['total_archived_size_mb'],
            "archive_count": info['archive_count'],
            "retention_days": info['retention_days'],
        },
        "current_snapshots": len(tracker.snapshots),
        "archives": info['archives'],
    }
    
    if output_file is None:
        output_file = f"archive_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    output_path = Path(output_file)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ エクスポート完了: {output_path}")


def main():
    """メインコマンド"""
    print("\n🔧 メトリクスアーカイブ管理ツール")
    print("="*60)
    
    # MetricTracker初期化
    config = get_config('metrics')
    tracker = MetricTracker()
    
    if len(sys.argv) < 2:
        # デフォルト表示
        show_archive_info(tracker)
        show_snapshots(tracker, limit=5)
    else:
        command = sys.argv[1].lower()
        
        if command == "info":
            show_archive_info(tracker)
            show_snapshots(tracker)
        
        elif command == "snapshots":
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            show_snapshots(tracker, limit=limit)
        
        elif command == "cleanup":
            confirm = input("\n古いアーカイブを削除しますか？ (y/n): ")
            if confirm.lower() == 'y':
                cleanup_old_data(tracker)
        
        elif command == "restore":
            if len(sys.argv) < 3:
                print("\n使用方法: python archive_util.py restore <archive_filename>")
                print(f"利用可能なアーカイブ:")
                info = tracker.get_archive_info()
                for archive in info['archives']:
                    print(f"  - {archive['filename']}")
            else:
                archive_name = sys.argv[2]
                restore_archive(tracker, archive_name)
        
        elif command == "export":
            output_file = sys.argv[2] if len(sys.argv) > 2 else None
            export_archive_summary(tracker, output_file)
        
        elif command == "help":
            print("\n使用可能なコマンド:")
            print(f"  python {sys.argv[0]} info          - アーカイブ情報を表示")
            print(f"  python {sys.argv[0]} snapshots [N] - 最近のNスナップショット表示（デフォルト10）")
            print(f"  python {sys.argv[0]} cleanup       - 古いアーカイブを削除")
            print(f"  python {sys.argv[0]} restore <name> - アーカイブから復元")
            print(f"  python {sys.argv[0]} export [file] - アーカイブサマリーをエクスポート")
            print(f"  python {sys.argv[0]} help         - このヘルプを表示")
        
        else:
            print(f"\n❌ 不明なコマンド: {command}")
            print(f"ヘルプを表示: python {sys.argv[0]} help")
    
    print("\n")


if __name__ == "__main__":
    main()
