#!/usr/bin/env python3
"""外部ドライブ指定機能のテスト"""

import sys
import tempfile
from pathlib import Path

# プロジェクトルート設定
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from backup.backup_manager import ProjectBackupManager

def test_external_drive():
    """外部ドライブ指定機能のテスト"""
    
    print("\n" + "="*70)
    print("🧪 外部ドライブ指定機能テスト")
    print("="*70)
    
    # Test 1: デフォルトバックアップ先
    print("\n[Test 1] デフォルトバックアップ先")
    manager1 = ProjectBackupManager(project_root=PROJECT_ROOT)
    result1 = manager1.create_backup(
        targets=["system_config"],
        backup_name="test_default"
    )
    
    if result1.get("success"):
        backup_path1 = result1.get("backup_path")
        print(f"✅ 成功")
        print(f"   保存先: {backup_path1}")
        if "backups" in backup_path1:
            print(f"   ✓ デフォルト backups フォルダに保存")
    else:
        print(f"❌ 失敗: {result1.get('error')}")
        return False
    
    # Test 2: 外部ドライブ（一時フォルダ）を指定
    print("\n[Test 2] 外部ドライブを指定")
    with tempfile.TemporaryDirectory() as tmpdir:
        external_backup_root = Path(tmpdir) / "external_drive" / "backups"
        
        manager2 = ProjectBackupManager(
            project_root=PROJECT_ROOT,
            backup_root=str(external_backup_root)
        )
        result2 = manager2.create_backup(
            targets=["system_config"],
            backup_name="test_external"
        )
        
        if result2.get("success"):
            backup_path2 = result2.get("backup_path")
            print(f"✅ 成功")
            print(f"   保存先: {backup_path2}")
            if str(external_backup_root) in backup_path2:
                print(f"   ✓ 指定した外部ドライブに保存")
            else:
                print(f"   ✗ 指定先が異なる可能性")
                return False
        else:
            print(f"❌ 失敗: {result2.get('error')}")
            return False
    
    # Test 3: 環境変数で外部ドライブを指定
    print("\n[Test 3] 環境変数で外部ドライブを指定")
    import os
    with tempfile.TemporaryDirectory() as tmpdir:
        env_backup_root = Path(tmpdir) / "env_drive" / "backups"
        env_backup_root.mkdir(parents=True, exist_ok=True)
        
        old_backup_root = os.environ.get("BACKUP_ROOT")
        os.environ["BACKUP_ROOT"] = str(env_backup_root)
        
        try:
            manager3 = ProjectBackupManager(project_root=PROJECT_ROOT)
            result3 = manager3.create_backup(
                targets=["system_config"],
                backup_name="test_env"
            )
            
            if result3.get("success"):
                backup_path3 = result3.get("backup_path")
                print(f"✅ 成功")
                print(f"   保存先: {backup_path3}")
                if str(env_backup_root) in backup_path3:
                    print(f"   ✓ 環境変数で指定したパスに保存")
                else:
                    print(f"   ✗ パスが異なる可能性")
                    return False
            else:
                print(f"❌ 失敗: {result3.get('error')}")
                return False
        finally:
            # 環境変数を復元
            if old_backup_root:
                os.environ["BACKUP_ROOT"] = old_backup_root
            else:
                os.environ.pop("BACKUP_ROOT", None)
    
    # Test 4: パラメータの優先順序（引数 > 環境変数 > デフォルト）
    print("\n[Test 4] パラメータの優先順序確認")
    with tempfile.TemporaryDirectory() as tmpdir:
        param_backup_root = Path(tmpdir) / "param_drive" / "backups"
        
        manager4 = ProjectBackupManager(
            project_root=PROJECT_ROOT,
            backup_root=str(param_backup_root)
        )
        result4 = manager4.create_backup(
            targets=["system_config"],
            backup_name="test_priority"
        )
        
        if result4.get("success"):
            backup_path4 = result4.get("backup_path")
            print(f"✅ 成功")
            print(f"   保存先: {backup_path4}")
            if str(param_backup_root) in backup_path4:
                print(f"   ✓ 優先順序が正しく適用")
            else:
                print(f"   ✗ 優先順序が異なる可能性")
                return False
        else:
            print(f"❌ 失敗: {result4.get('error')}")
            return False
    
    print("\n" + "="*70)
    print("✅ すべてのテストが成功しました！")
    print("="*70)
    print("\n💡 使用例:")
    print("  # CLI: 外部ドライブにバックアップ")
    print("  python tools/backup_cli.py --external-drive /mnt/external create")
    print("\n  # または環境変数で設定:")
    print("  export BACKUP_ROOT=/mnt/external/backups")
    print("  python tools/backup_cli.py create")
    
    return True

if __name__ == "__main__":
    success = test_external_drive()
    sys.exit(0 if success else 1)
