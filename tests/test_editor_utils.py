import pytest
from pathlib import Path
import os
import time
from dotenv import load_dotenv
load_dotenv()

from src.rag.retriever import Retriever
from src.utils.editor_utils import (
    get_document_full_text,
    find_physical_file,
    save_and_reindex_document
)
from src.utils.path_utils import PROJECT_ROOT

@pytest.fixture(scope="module")
def shared_retriever():
    """テスト用のRetrieverインスタンスを初期化"""
    corpus_path = PROJECT_ROOT / "corpus"
    index_path = corpus_path / "corpus.index"
    meta_path = corpus_path / "corpus_meta.json"
    
    return Retriever(index_path=index_path, meta_path=meta_path)


def test_document_reconstruction_and_reindexing(shared_retriever):
    retriever = shared_retriever
    test_source = "temp_editor_integration_test.txt"
    initial_text = "これはRAGエージェントのインラインエディタ機能の統合テストです。\n初期バージョンナレッジ。"
    
    # 事前のクリーンアップ
    retriever.delete_source(test_source)
    
    try:
        # 1. 初期テキストを登録
        from src.utils.text_utils import _chunk_text
        chunks = _chunk_text(initial_text)
        added = retriever.add_texts(chunks, source_info={"source": test_source})
        assert added > 0
        
        # 2. テキストが正しく結合復元できるかテスト
        restored_text = get_document_full_text(test_source)
        assert initial_text in restored_text
        
        # 3. 編集保存＆再インデックスをテスト
        updated_text = "これはRAGエージェントのインラインエディタ機能の統合テストです。\n更新された第二バージョンのナレッジデータ。"
        res = save_and_reindex_document(retriever, test_source, updated_text)
        
        assert res["success"] is True
        assert res["deleted_chunks"] == added
        assert res["added_chunks"] > 0
        
        # 4. 更新後のテキストが結合復元できるかテスト
        restored_updated = get_document_full_text(test_source)
        assert "更新された第二バージョン" in restored_updated
        assert "初期バージョンナレッジ" not in restored_updated
        
        # 5. RAG検索で更新後のキーワードがヒットするか確認
        search_res = retriever.search("第二バージョン", top_k=1)
        assert len(search_res) > 0
        assert test_source in [doc.get("meta", {}).get("source") for doc in search_res]

    finally:
        # クリーンアップ
        retriever.delete_source(test_source)


def test_find_physical_file():
    # README.md がプロジェクトルートで見つかることを確認
    readme_path = find_physical_file("README.md")
    assert readme_path is not None
    assert readme_path.name == "README.md"
    assert readme_path.exists()
    
    # 存在しないファイルは None になることを確認
    assert find_physical_file("non_existent_file_xyz_123.md") is None
