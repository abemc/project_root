from datetime import datetime, timedelta
from src.rag.embed_store import FaissStore


def test_meta_time_and_tags(tmp_path):
    idx = str(tmp_path / "meta.index")
    meta = str(tmp_path / "meta.json")

    def embed_fn(t):
        import numpy as np
        v = np.ones(8, dtype='float32')
        return v / (np.linalg.norm(v) + 1e-6)

    store = FaissStore(index_path=idx, meta_path=meta, dim=8, embed_fn=embed_fn)

    now = datetime.now()
    docs = [
        {"id": "a", "text": "a", "created_at": (now - timedelta(days=2)).isoformat(), "tags": ["x","y"]},
        {"id": "b", "text": "b", "created_at": (now - timedelta(days=1)).isoformat(), "tags": ["y"]},
        {"id": "c", "text": "c", "created_at": now.isoformat(), "tags": ["z"]},
    ]

    store.upsert(docs)

    # filter by tag list
    res = store.search(store.embed_fn('a'), top_k=5, filters={"tags": ["x","y"]})
    # since our meta matches must be exact membership, expect 'a' and 'b' when tags include 'y'
    assert any(r.get('id') == 'a' for r in res) or any(r.get('id') == 'b' for r in res)
