#!/usr/bin/env python3
"""バックアップマネージャーの後方互換性テスト"""

import sys
from pathlib import Path
import tempfile

# パスの追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from backup.backup_manager import ProjectBackupManager

def test_compress_parameter():
    """compress パラメータの後方互換性テスト"""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ProjectBackupManager(
            project_root=project_root,
            backup_root=tmpdir
        )
        
        print("🧪 Test 1: compression=True パラメータ")
        try:
            result1 = manager.create_backup(
                targets=["system_config"],
                backup_name="test_compression",
                compression=True
            )
            if result1.get("success"):
                print(f"✅ 成功: {result1.get('backup_id')}")
            else:
                print(f"❌ 失敗: {result1}")
                return False
        except Exception as e:
            print(f"❌ 失敗: {e}")
            return False
        
        print("\n🧪 Test 2: compress=True パラメータ (後方互換性)")
        try:
            result2 = manager.create_backup(
                targets=["system_config"],
                backup_name="test_compress",
                compress=True
            )
            if result2.get("success"):
                print(f"✅ 成功: {result2.get('backup_id')}")
            else:
                print(f"❌ 失敗: {result2}")
                return False
        except Exception as e:
            print(f"❌ 失敗: {e}")
            return False
        
        print("\n🧪 Test 3: 両パラメータ指定時は compression が優先")
        try:
            result3 = manager.create_backup(
                targets=["system_config"],
                backup_name="test_both",
                compression=False,
                compress=True  # compression=False が優先される
            )
            if result3.get("success"):
                backup_path = result3.get("backup_path", "")
                if ".tar.gz" in backup_path:
                    print(f"❌ 失敗: compression=False が優先されるべき")
                    return False
                else:
                    print(f"✅ 成功: compression パラメータが正しく優先された")
            else:
                print(f"❌ 失敗: {result3}")
                return False
        except Exception as e:
            print(f"❌ 失敗: {e}")
            return False
        
        print("\n🧪 Test 4: compression=False パラメータ")
        try:
            result4 = manager.create_backup(
                targets=["system_config"],
                backup_name="test_no_compress",
                compression=False
            )
            if result4.get("success"):
                print(f"✅ 成功: {result4.get('backup_id')}")
            else:
                print(f"❌ 失敗: {result4}")
                return False
        except Exception as e:
            print(f"❌ 失敗: {e}")
            return False
        
        print("\n✅ すべてのテストが成功しました！")
        return True

if __name__ == "__main__":
    success = test_compress_parameter()
    sys.exit(0 if success else 1)

