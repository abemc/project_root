from src.rag.embed_store import FaissStore


def test_upsert_overwrite(tmp_path):
    idx = str(tmp_path / "upsert.index")
    meta = str(tmp_path / "upsert_meta.json")
    store = FaissStore(index_path=idx, meta_path=meta, dim=8)

    # initial upsert
    ids1 = store.upsert([{"id": "a", "text": "old text", "tag": "v1"}])
    assert ids1 == ["a"]
    assert len(store.meta) == 1
    assert store.meta[0]["text"] == "old text"

    # upsert with same id should overwrite metadata, not duplicate
    ids2 = store.upsert([{"id": "a", "text": "new text", "tag": "v2"}])
    assert ids2 == ["a"]
    assert len(store.meta) == 1
    assert store.meta[0]["text"] == "new text"
    assert store.meta[0]["tag"] == "v2"
