from src.rag.ingest import ingest_documents
from src.rag.embed_store import FaissStore


def test_ingest_and_retrieve(tmp_path):
    idx = str(tmp_path / "ingest.index")
    meta = str(tmp_path / "ingest_meta.json")

    # use deterministic embed function
    def embed_fn(text):
        import numpy as np
        v = (np.frombuffer(text.encode('utf-8'), dtype='uint8').astype('float32')[:8])
        if v.size < 8:
            v = np.pad(v, (0, 8 - v.size), constant_values=1.0)
        v = v / (np.linalg.norm(v) + 1e-6)
        return v

    store = FaissStore(index_path=idx, meta_path=meta, dim=8, embed_fn=embed_fn)

    docs = [
        {"id": "doc1", "text": "apple banana", "domain": "food", "tags": ["fruit"]},
        {"id": "doc2", "text": "truck car", "domain": "transport", "tags": ["vehicle"]},
    ]

    ids = ingest_documents(docs, store=store, chunk_size=10, overlap=2)
    assert any('doc1' in i for i in ids)

    qvec = store.embed_fn('apple')
    res = store.search(qvec, top_k=3, filters={"domain": "food"})
    assert any(r.get('domain') == 'food' for r in res)
