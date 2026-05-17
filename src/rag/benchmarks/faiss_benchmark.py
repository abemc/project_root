"""Simple FaissStore benchmark: upsert, search, delete timings.

Usage: run as a script. Adjust N for scale.
"""
import time
import random
from src.rag.embed_store import FaissStore


def make_docs(n, prefix='doc'):
    docs = []
    for i in range(n):
        docs.append({'id': f'{prefix}_{i}', 'text': f'sample text {i}', 'tag': random.choice(['a','b','c'])})
    return docs


def bench(n=2000):
    print(f'Benchmarking with N={n}')
    s = FaissStore(index_path='corpus/bench.index', meta_path='corpus/bench_meta.json', dim=8)

    docs = make_docs(n)

    t0 = time.time()
    ids = s.upsert(docs)
    t_upsert = time.time() - t0
    print(f'Upsert {n} docs: {t_upsert:.3f}s ({t_upsert/n*1000:.3f} ms/op)')

    # search bench
    q = s.embed_fn('sample text 1')
    trials = 100
    t0 = time.time()
    for _ in range(trials):
        _ = s.search(q, top_k=5)
    t_search = time.time() - t0
    print(f'{trials} searches: {t_search:.3f}s ({t_search/trials*1000:.3f} ms/search)')

    # delete bench
    del_ids = [f'doc_{i}' for i in range(0, n, 10)]
    t0 = time.time()
    s.delete(del_ids)
    t_delete = time.time() - t0
    print(f'Delete {len(del_ids)} ids: {t_delete:.3f}s ({t_delete/len(del_ids)*1000:.3f} ms/op)')

    return {'n': n, 'upsert_s': t_upsert, 'search_s': t_search, 'delete_s': t_delete}


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--n', type=int, default=2000)
    args = p.parse_args()
    bench(args.n)
