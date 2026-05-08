"""環境依存のパス設定を一元管理するモジュール"""
import os
from pathlib import Path

# プロジェクトルート
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

def get_corpus_path() -> Path:
    """
    コーパスデータのパスを環境変数または自動検出で取得
    
    優先順位:
    1. RAG_CORPUS_PATH環境変数
    2. ローカルプロジェクト内のrag_corpus
    3. ローカルプロジェクト内のcorpus
    4. ローカルプロジェクト内のsrc/embeddings
    5. フォールバック: project_root/rag_corpus
    """
    # 1. 環境変数
    if env_path := os.getenv("RAG_CORPUS_PATH"):
        path = Path(env_path)
        if path.exists():
            return path
    
    # 2-4. ローカル候補パス
    candidates = [
        PROJECT_ROOT / "rag_corpus",
        PROJECT_ROOT / "corpus",
        PROJECT_ROOT / "src" / "embeddings",
    ]
    
    for candidate in candidates:
        if (candidate / "corpus.index").exists() and (candidate / "corpus_meta.json").exists():
            return candidate
    
    # 5. フォールバック（存在しなくても返却）
    return candidates[0]

def get_corpus_index_path() -> Path:
    """コーパスインデックスのパスを取得"""
    corpus_path = get_corpus_path()
    return corpus_path / "corpus.index"

def get_corpus_meta_path() -> Path:
    """コーパスメタデータのパスを取得"""
    corpus_path = get_corpus_path()
    return corpus_path / "corpus_meta.json"

def get_embeddings_path() -> Path:
    """埋め込みベクトルの保存先パスを取得"""
    corpus_path = get_corpus_path()
    embeddings_dir = corpus_path / "embeddings"
    embeddings_dir.mkdir(parents=True, exist_ok=True)
    return embeddings_dir

def get_chunks_path() -> Path:
    """テキストチャンク保存先ディレクトリを取得"""
    corpus_path = get_corpus_path()
    chunks_dir = corpus_path / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    return chunks_dir

def get_normalized_path() -> Path:
    """正規化テキスト保存先ディレクトリを取得"""
    corpus_path = get_corpus_path()
    normalized_dir = corpus_path / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    return normalized_dir

def get_meta_dir() -> Path:
    """メタデータ保存先ディレクトリを取得"""
    corpus_path = get_corpus_path()
    meta_dir = corpus_path / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    return meta_dir

# グローバル定数
CORPUS_ROOT = get_corpus_path()
CORPUS_INDEX_PATH = get_corpus_index_path()
CORPUS_META_PATH = get_corpus_meta_path()
