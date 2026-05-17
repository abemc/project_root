from src.rag.embed_store import FaissStore
import numpy as np
import tempfile


def test_faissstore_upsert_and_search(tmp_path):
    idx_path = str(tmp_path / 'embed.index')
    meta_path = str(tmp_path / 'embed_meta.json')
    store = FaissStore(index_path=idx_path, meta_path=meta_path, dim=8)

    docs = [
        {'text': 'hello world', 'meta': {'source': 'test'}},
        {'text': 'goodbye world', 'meta': {'source': 'test'}},
    ]
    ids = store.upsert(docs)
    assert len(ids) == 2

    # search using embedding of 'hello world'
    qv = store.embed_fn('hello world')
    res = store.search(qv, top_k=2)
    assert len(res) >= 1
    assert 'id' in res[0]
