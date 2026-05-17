import numpy as np
from src.rag.multi_domain_retriever import MultiDomainRetriever


def _deterministic_embed(seed: int = 42, dim: int = 1024):
    rng = np.random.RandomState(seed)
    def _fn(text: str):
        v = rng.rand(dim).astype('float32')
        v = v / (np.linalg.norm(v) + 1e-6)
        return v
    return _fn


def test_multi_retriever_with_filters(tmp_path):
    embed_fn = _deterministic_embed(seed=1, dim=1024)
    mr = MultiDomainRetriever(default_domains=['testdomain'], embed_fn=embed_fn)

    # add two docs with different tags
    docs = ["apple orange", "car truck"]
    metas = [
        {"id": "d1", "tag": "fruit"},
        {"id": "d2", "tag": "vehicle"},
    ]

    mr.add_documents_to_domain('testdomain', docs, metadata=metas)

    res_all = mr.retrieve_from_domain('apple', 'testdomain', top_k=2)
    assert any(r.get('id') == 'd1' for r in res_all.results)

    res_filtered = mr.retrieve_from_domain('apple', 'testdomain', top_k=2, filters={'tag': 'fruit'})
    assert all(r.get('tag') == 'fruit' for r in res_filtered.results)
