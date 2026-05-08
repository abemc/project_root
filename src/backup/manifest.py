"""バックアップマニフェスト管理"""

from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
import json
from typing import Dict, List, Optional


@dataclass
class BackupItem:
    """バックアップ対象アイテム"""
    source_path: str           # 元のパス
    relative_path: str         # 相対パス
    file_count: int = 0        # ファイル数
    total_size: int = 0        # 合計サイズ（バイト）
    excluded: int = 0          # 除外ファイル数
    item_type: str = "unknown" # folder, file, unknown


@dataclass
class BackupManifest:
    """バックアップメタデータ"""
    backup_id: str
    timestamp: str             # ISO形式
    version: str               # プロジェクトバージョン
    total_size: int            # 合計バイト数
    items: List[BackupItem] = field(default_factory=list)
    config: Dict = field(default_factory=dict)  # 設定情報
    notes: str = ""
    
    @classmethod
    def create(
        cls,
        backup_id: str,
        version: str,
        config: Dict = None,
        notes: str = ""
    ):
        """新しいマニフェストを作成"""
        return cls(
            backup_id=backup_id,
            timestamp=datetime.now().isoformat(),
            version=version,
            total_size=0,
            items=[],
            config=config or {},
            notes=notes
        )
    
    def add_item(self, item: BackupItem):
        """アイテムを追加"""
        self.items.append(item)
        self.total_size += item.total_size
    
    def save(self, manifest_path: Path):
        """マニフェストをJSONで保存"""
        manifest_dir = Path(manifest_path).parent
        manifest_dir.mkdir(parents=True, exist_ok=True)
        
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, manifest_path: Path):
        """マニフェストをJSONから読み込み"""
        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # BackupItemを再構築
        items = [BackupItem(**item) for item in data.get('items', [])]
        data['items'] = items
        
        return cls(**data)
    
    def get_summary(self) -> Dict:
        """サマリー情報を取得"""
        return {
            "backup_id": self.backup_id,
            "timestamp": self.timestamp,
            "version": self.version,
            "item_count": len(self.items),
            "total_size_mb": round(self.total_size / (1024 ** 2), 2),
            "total_files": sum(item.file_count for item in self.items),
            "notes": self.notes
        }
