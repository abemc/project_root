import numpy as np
import os
from pathlib import Path

from src.rag.embed_store import FaissStore
from src.rag.multi_domain_retriever import DomainIndex


def _rand_vec(dim):
    v = np.random.rand(dim).astype('float32')
    v = v / (np.linalg.norm(v) + 1e-6)
    return v


def test_faissstore_filters(tmp_path):
    idx_path = str(tmp_path / "faiss_test.index")
    meta_path = str(tmp_path / "faiss_test_meta.json")
    store = FaissStore(index_path=idx_path, meta_path=meta_path, dim=8)

    docs = [
        {"id": "a", "text": "apple banana", "tag": "fruit"},
        {"id": "b", "text": "banana orange", "tag": "fruit"},
        {"id": "c", "text": "car truck", "tag": "vehicle"},
    ]
    ids = store.upsert(docs)
    assert len(ids) == 3

    q = store.embed_fn("apple")
    all_res = store.search(q, top_k=3)
    assert len(all_res) >= 1

    fruit_res = store.search(q, top_k=3, filters={"tag": "fruit"})
    assert all(r.get('tag') == 'fruit' for r in fruit_res)


def test_domainindex_filters(tmp_path):
    # DomainIndex uses embedding_dim 1024 by default; create accordingly
    domain = "testdomain"
    index_path = Path(tmp_path) / f"corpus_{domain}.index"
    di = DomainIndex(domain, index_path=index_path)

    # prepare 3 vectors and metadata
    emb_dim = di.embedding_dim
    vecs = np.vstack([_rand_vec(emb_dim) for _ in range(3)])
    metas = [
        {"id": "x", "category": "alpha"},
        {"id": "y", "category": "alpha"},
        {"id": "z", "category": "beta"},
    ]

    di.add_documents(vecs, metas)

    q = vecs[0]
    idxs, dists = di.search(q, top_k=3)
    assert len(idxs) >= 1

    # filter by category
    f_idxs, f_dists = di.search(q, top_k=3, filters={"category": "alpha"})
    assert all(di.meta[i]['category'] == 'alpha' for i in f_idxs)
