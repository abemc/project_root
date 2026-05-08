#!/usr/bin/env python3
"""プロジェクトバックアップ管理ツール"""

import sys
import argparse
import logging
import os
from pathlib import Path
from typing import Optional
from datetime import datetime

# プロジェクトルート設定
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from backup.backup_manager import ProjectBackupManager

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def resolve_external_drive_path(drive_spec: str) -> Path:
    """
    外部ドライブパスを解決
    
    WSL環境では Windows ドライブ (D:) を /mnt/d に自動変換
    
    Args:
        drive_spec: ドライブ指定（例: /mnt/external, D:, D:\\, /Volumes/External）
    
    Returns:
        解決されたパス + backups/ サブディレクトリ
        
    Raises:
        FileNotFoundError: ドライブパスが存在しない場合
    """
    if not drive_spec:
        return None
    
    drive_spec = drive_spec.strip()
    
    # Windows ドライブ指定 (D:, D:\\, etc.) を WSL パスに変換
    if len(drive_spec) >= 2 and drive_spec[1] == ':':
        # D: → /mnt/d, D:\\ → /mnt/d など
        drive_letter = drive_spec[0].lower()
        # WSL環境での Windows ドライブマウント先
        drive_path = Path(f"/mnt/{drive_letter}")
        logger.info(f"Windows ドライブを検出: {drive_spec} → {drive_path}")
        
        # ドライブが存在するか確認
        if not drive_path.exists():
            # 利用可能なドライブを列挙
            available_drives = []
            for letter in "abcdefghijklmnopqrstuvwxyz":
                mnt_path = Path(f"/mnt/{letter}")
                if mnt_path.exists() and mnt_path.is_dir():
                    try:
                        next(mnt_path.iterdir())
                        available_drives.append(letter.upper())
                    except PermissionError:
                        available_drives.append(f"{letter.upper()} (アクセス拒否)")
            
            error_msg = f"\n❌ ドライブ {drive_spec} はマウントされていません。\n"
            if available_drives:
                error_msg += f"\n📁 利用可能なドライブ:\n"
                for drive in available_drives:
                    error_msg += f"   - {drive}:\n"
            else:
                error_msg += "\n⚠️ マウントされたドライブが見つかりません。\n"
            
            error_msg += "\n💡 ヒント:\n"
            error_msg += "  - WSL から Windows ドライブをマウント確認\n"
            error_msg += "  - または絶対パスを指定: /mnt/external_drive/\n"
            error_msg += "  - または環境変数 BACKUP_ROOT で設定\n"
            
            raise FileNotFoundError(error_msg)
    else:
        # Unix パス（/mnt/external など）
        drive_path = Path(drive_spec)
        
        # パスが存在するか確認
        if not drive_path.exists():
            raise FileNotFoundError(
                f"\n❌ パス '{drive_spec}' が見つかりません。\n"
                f"\n💡 ヒント:\n"
                f"  - パスが正しいか確認してください\n"
                f"  - または mkdir -p '{drive_spec}' で作成してください\n"
            )
    
    # backups/ サブディレクトリを追加（まだない場合）
    if not str(drive_path).endswith(("backups", "backups/")):
        drive_path = drive_path / "backups"
    
    return drive_path


class BackupCLI:
    """バックアップCLI"""
    
    def __init__(self, project_root: str = None, backup_root: str = None):
        self.project_root = Path(project_root or PROJECT_ROOT)
        self.backup_root = Path(backup_root) if backup_root else None
        self.manager = ProjectBackupManager(self.project_root, self.backup_root)
    
    def create(
        self,
        targets: Optional[str] = None,
        name: Optional[str] = None,
        include_kb: bool = True,
        compress: bool = True,
        notes: str = ""
    ):
        """バックアップを作成"""
        target_list = targets.split(",") if targets else None
        
        print(f"\n{'='*60}")
        print("🔄 プロジェクトバックアップを開始します")
        print(f"{'='*60}")
        
        try:
            result = self.manager.create_backup(
                targets=target_list,
                backup_name=name,
                include_kb=include_kb,
                compression=compress,
                notes=notes
            )
            
            if result.get("success"):
                print(f"\n✅ バックアップ完了！")
                print(f"\n📋 バックアップ情報:")
                print(f"  ID: {result['backup_id']}")
                print(f"  時刻: {result['timestamp']}")
                print(f"  サイズ: {result['total_size'] / (1024**2):.2f} MB")
                print(f"  ファイル数: {result['file_count']}")
                
                # 保存先を絶対パスで表示
                backup_path = result['backup_path']
                backup_abs_path = Path(backup_path).resolve()
                print(f"  保存先: {backup_path}")
                print(f"  絶対パス: {backup_abs_path}")
                
                # ファイルが本当に存在するか確認
                if backup_abs_path.exists():
                    if backup_abs_path.is_file():
                        file_size_mb = backup_abs_path.stat().st_size / (1024**2)
                        print(f"  ✅ 圧縮ファイル: {file_size_mb:.2f} MB")
                    elif backup_abs_path.is_dir():
                        print(f"  ✅ ディレクトリ: 内容確認可能")
                else:
                    print(f"  ⚠️ ファイルが見つかりません（パスをご確認ください）")
                if notes:
                    print(f"  説明: {notes}")
            else:
                print(f"\n❌ エラー: {result.get('error', '不明なエラー')}")
                return 1
            
        except Exception as e:
            print(f"\n❌ エラー: {e}")
            return 1
        
        return 0
    
    def list_backups(self):
        """バックアップ一覧を表示"""
        backups = self.manager.list_backups()
        
        if not backups:
            print("ℹ️ バックアップがありません")
            return 0
        
        print(f"\n{'='*80}")
        print("📦 利用可能なバックアップ")
        print(f"{'='*80}\n")
        
        for i, backup in enumerate(backups, 1):
            print(f"{i}. {backup.get('backup_id', 'Unknown')}")
            print(f"   時刻: {backup.get('timestamp', 'N/A')}")
            print(f"   サイズ: {backup.get('total_size_mb', backup.get('size_mb', 0))} MB")
            print(f"   ファイル数: {backup.get('total_files', 'N/A')}")
            print(f"   バージョン: {backup.get('version', 'Unknown')}")
            if backup.get('notes'):
                print(f"   説明: {backup['notes']}")
            print()
        
        return 0
    
    def restore(self, backup_id: str, restore_root: Optional[str] = None, verify: bool = True):
        """バックアップをリストア"""
        print(f"\n{'='*60}")
        print(f"🔄 バックアップをリストアします: {backup_id}")
        print(f"{'='*60}\n")
        
        # 確認
        response = input("⚠️ 本当にリストアしますか？ (yes/no): ").strip().lower()
        if response != "yes":
            print("キャンセルしました")
            return 0
        
        try:
            success = self.manager.restore_backup(
                backup_id,
                restore_root=restore_root,
                verify=verify
            )
            
            if success:
                print(f"\n✅ リストア完了！")
                print(f"復元先: {restore_root or self.project_root}")
            else:
                print(f"\n❌ リストア失敗")
                return 1
            
        except Exception as e:
            print(f"\n❌ エラー: {e}")
            return 1
        
        return 0
    
    def info(self, backup_id: str):
        """バックアップ情報を表示"""
        backup_source = self.manager._find_backup(backup_id)
        if not backup_source:
            print(f"❌ バックアップが見つかりません: {backup_id}")
            return 1
        
        # マニフェストを読み込み
        if str(backup_source).endswith(".tar.gz"):
            # 圧縮ファイルの情報を表示
            print(f"\n📦 バックアップ情報: {backup_id}")
            print(f"  サイズ: {backup_source.stat().st_size / (1024**2):.2f} MB")
            print(f"  形式: 圧縮 (tar.gz)")
        else:
            manifest_path = backup_source / "manifest.json"
            if manifest_path.exists():
                from backup.manifest import BackupManifest
                manifest = BackupManifest.load(manifest_path)
                
                print(f"\n📋 バックアップ情報")
                print(f"  ID: {manifest.backup_id}")
                print(f"  時刻: {manifest.timestamp}")
                print(f"  バージョン: {manifest.version}")
                print(f"  サイズ: {manifest.total_size / (1024**2):.2f} MB")
                print(f"  要素数: {len(manifest.items)}")
                
                if manifest.items:
                    print(f"\n  📁 含まれるもの:")
                    for item in manifest.items:
                        print(f"    - {item.relative_path}")
                        print(f"      ファイル: {item.file_count}, サイズ: {item.total_size / (1024**2):.2f} MB")
        
        return 0
    
    def delete(self, backup_id: str):
        """バックアップを削除"""
        print(f"\n⚠️ バックアップを削除します: {backup_id}")
        response = input("本当に削除しますか？ (yes/no): ").strip().lower()
        if response != "yes":
            print("キャンセルしました")
            return 0
        
        if self.manager.delete_backup(backup_id):
            print("✅ バックアップを削除しました")
            return 0
        else:
            print("❌ 削除失敗")
            return 1
    
    def cleanup(self, keep_days: int = 30, keep_count: int = 5):
        """古いバックアップをクリーンアップ"""
        print(f"\n🧹 古いバックアップをクリーンアップします")
        print(f"  保持期間: {keep_days}日")
        print(f"  最小保持数: {keep_count}個")
        
        response = input("\nクリーンアップを実行しますか？ (yes/no): ").strip().lower()
        if response != "yes":
            print("キャンセルしました")
            return 0
        
        self.manager.cleanup_old_backups(keep_days=keep_days, keep_count=keep_count)
        print("✅ クリーンアップ完了")
        return 0


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="プロジェクトバックアップ管理ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # バックアップを作成（推奨設定）
  python backup_cli.py create --compress
  
  # 外部ドライブにバックアップ（Linux/Mac: /mnt/external）
  python backup_cli.py --external-drive /mnt/external create --compress
  
  # 外部ドライブにバックアップ（Windows: D:\\）
  python backup_cli.py --drive D: create --compress
  
  # 特定のターゲットのみバックアップ + 外部ドライブ
  python backup_cli.py --external-drive /mnt/external_drive/backups create --targets "system_config,source_code,documentation"
  
  # 環境変数でデフォルまドライブ設定（.env ファイルに追加）
  # BACKUP_ROOT=/mnt/external_drive/backups
  python backup_cli.py create --compress
  
  # バックアップ一覧を表示
  python backup_cli.py list
  
  # バックアップ情報を表示
  python backup_cli.py info backup_id
  
  # バックアップをリストア
  python backup_cli.py restore backup_id
  
  # バックアップを削除
  python backup_cli.py delete backup_id
  
  # 古いバックアップをクリーンアップ
  python backup_cli.py cleanup --keep-days 30 --keep-count 5
        """
    )
    
    # グローバルオプション
    parser.add_argument(
        "--backup-root",
        help="バックアップ保存先パス（デフォルト: project_root/backups 或いは 環境変数 BACKUP_ROOT）",
        default=None
    )
    
    parser.add_argument(
        "--external-drive",
        "--drive",
        dest="external_drive",
        metavar="PATH",
        help="外部ドライブパス（例: /mnt/external, D:, /Volumes/External）",
        default=None
    )
    
    subparsers = parser.add_subparsers(dest="command", help="コマンド")
    
    # create サブコマンド
    create_parser = subparsers.add_parser("create", help="バックアップを作成")
    create_parser.add_argument(
        "--targets",
        help="バックアップ対象（カンマ区切り）",
        default=None
    )
    create_parser.add_argument(
        "--name",
        help="バックアップ名",
        default=None
    )
    create_parser.add_argument(
        "--no-kb",
        action="store_true",
        help="知識ベースを除外"
    )
    
    # 圧縮オプション（同じ dest で両立）
    create_parser.add_argument(
        "--compress",
        dest="compress",
        action="store_true",
        default=True,
        help="圧縮を有効化（デフォルト）"
    )
    create_parser.add_argument(
        "--no-compress",
        dest="compress",
        action="store_false",
        help="圧縮を無効化"
    )
    
    create_parser.add_argument(
        "--notes",
        help="バックアップの説明",
        default=""
    )
    
    # list サブコマンド
    subparsers.add_parser("list", help="バックアップ一覧")
    
    # info サブコマンド
    info_parser = subparsers.add_parser("info", help="バックアップ情報")
    info_parser.add_argument("backup_id", help="バックアップID")
    
    # restore サブコマンド
    restore_parser = subparsers.add_parser("restore", help="バックアップをリストア")
    restore_parser.add_argument("backup_id", help="バックアップID")
    restore_parser.add_argument("--restore-root", help="リストア先", default=None)
    
    # delete サブコマンド
    delete_parser = subparsers.add_parser("delete", help="バックアップを削除")
    delete_parser.add_argument("backup_id", help="バックアップID")
    
    # cleanup サブコマンド
    cleanup_parser = subparsers.add_parser("cleanup", help="古いバックアップをクリーンアップ")
    cleanup_parser.add_argument(
        "--keep-days",
        type=int,
        default=30,
        help="保持期間（日）"
    )
    cleanup_parser.add_argument(
        "--keep-count",
        type=int,
        default=5,
        help="最小保持数"
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    # ドライブ/パス指定とエラーハンドリング
    backup_root = None
    try:
        if hasattr(args, 'external_drive') and args.external_drive:
            backup_root = str(resolve_external_drive_path(args.external_drive))
            print(f"📁 外部ドライブモード: {backup_root}")
        elif args.backup_root:
            backup_root = args.backup_root
        elif os.environ.get("BACKUP_ROOT"):
            backup_root = os.environ["BACKUP_ROOT"]
            print(f"📁 環境変数 BACKUP_ROOT ロード: {backup_root}")
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1
    
    try:
        cli = BackupCLI(backup_root=backup_root)
    except (FileNotFoundError, PermissionError) as e:
        print(f"\n❌ エラー: {e}", file=sys.stderr)
        return 1
    
    if args.command == "create":
        return cli.create(
            targets=args.targets,
            name=args.name,
            include_kb=not args.no_kb,
            compress=args.compress,
            notes=args.notes
        )
    elif args.command == "list":
        return cli.list_backups()
    elif args.command == "info":
        return cli.info(args.backup_id)
    elif args.command == "restore":
        return cli.restore(args.backup_id, args.restore_root)
    elif args.command == "delete":
        return cli.delete(args.backup_id)
    elif args.command == "cleanup":
        return cli.cleanup(args.keep_days, args.keep_count)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
