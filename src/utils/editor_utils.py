import json
import os
import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from src.utils.path_utils import PROJECT_ROOT
from src.utils.text_utils import _chunk_text

DEFAULT_CORPUS_META_PATH = PROJECT_ROOT / "corpus" / "corpus_meta.json"

def get_document_full_text(source_name: str, meta_path: Path = DEFAULT_CORPUS_META_PATH) -> str:
    """
    RAGコーパスメタデータから、指定されたソースファイルの全チャンクをロードして結合する。
    物理ファイルが存在しない場合でも、登録されたテキストを復元可能にします。
    """
    try:
        if not meta_path.exists():
            return ""
        with open(meta_path, "r", encoding="utf-8") as f:
            all_chunks = json.load(f)
        
        if not isinstance(all_chunks, list):
            return ""
            
        # 該当ソースのチャンクをフィルタ
        src_chunks = []
        for chunk in all_chunks:
            meta_info = chunk.get("meta", {})
            src = meta_info.get("source") or chunk.get("source", "unknown")
            if src == source_name:
                src_chunks.append(chunk)
                
        # 登録順（ファイルの先頭からの順序）に結合
        # 順序の整合性のために、そのまま順番に結合します
        return "\n\n".join(c.get("text", "") for c in src_chunks)
    except Exception as e:
        print(f"[Error] Failed to get document full text: {e}")
        return ""

def find_physical_file(source_name: str) -> Optional[Path]:
    """
    プロジェクト内の主要なナレッジ置き場から、ソース名に一致する物理ファイルを検索する。
    """
    search_paths = [
        PROJECT_ROOT / "docs" / source_name,
        PROJECT_ROOT / "rag_corpus" / source_name,
        PROJECT_ROOT / "rag_corpus" / "downloads" / source_name,
        PROJECT_ROOT / "corpus" / source_name,
        PROJECT_ROOT / source_name
    ]
    for p in search_paths:
        if p.exists() and p.is_file():
            return p
    return None

def save_and_reindex_document(retriever, source_name: str, new_text: str) -> Dict[str, Any]:
    """
    ドキュメントの新しいテキストを保存し、RAGコーパスの再インデックスを実行する。
    """
    if not source_name:
        return {"success": False, "error": "ソース名が空です。"}
    if not new_text.strip():
        return {"success": False, "error": "保存するテキストが空です。"}

    try:
        # 1. 物理ファイルが存在する場合は上書き
        physical_path = find_physical_file(source_name)
        if physical_path:
            try:
                physical_path.write_text(new_text, encoding="utf-8")
                print(f"Physical file saved to: {physical_path}")
            except Exception as e:
                return {"success": False, "error": f"物理ファイルの保存に失敗しました: {e}"}

        # 2. 古いインデックスの削除
        deleted_count = retriever.delete_source(source_name)
        print(f"Deleted {deleted_count} old chunks for {source_name}")

        # 3. 編集されたテキストをチャンク分割
        chunks = _chunk_text(new_text)
        
        # 4. 新しいインデックスとして追加登録
        source_info = {
            "source": source_name,
            "updated_at": datetime.datetime.now().isoformat(),
        }
        if physical_path:
            source_info["path"] = str(physical_path.relative_to(PROJECT_ROOT))
            
        added_count = retriever.add_texts(chunks, source_info=source_info)
        print(f"Added {added_count} new chunks for {source_name}")

        # 5. インデックスの保存
        retriever.save()

        return {
            "success": True,
            "deleted_chunks": deleted_count,
            "added_chunks": added_count,
            "physical_updated": bool(physical_path),
            "physical_path": str(physical_path) if physical_path else None
        }
    except Exception as e:
        import traceback
        err_details = traceback.format_exc()
        print(f"[Error] Reindexing failed: {e}\n{err_details}")
        return {"success": False, "error": f"再インデックス処理で例外が発生しました: {e}"}
