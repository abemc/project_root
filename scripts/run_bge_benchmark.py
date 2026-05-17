"""Run a Faiss upsert/search/delete benchmark using a real batched embedder.

Usage:
  PYTHONPATH=. python scripts/run_bge_benchmark.py --n 100000 --model BAAI/bge-m3 --batch_size 64
"""
import time
import argparse
import random
from src.rag.embedding_backend import BatchedEmbedder
from src.rag.embed_store import FaissStore


def make_docs(n, prefix='doc'):
    docs = []
    for i in range(n):
        docs.append({'id': f'{prefix}_{i}', 'text': f'sample text {i}', 'tag': random.choice(['a','b','c'])})
    return docs


def run(n=2000, model_name='BAAI/bge-m3', batch_size=32, device=None, upsert_batch_size=4096):
    print(f'Initializing BatchedEmbedder(model={model_name}, batch_size={batch_size}, device={device})')
    be = BatchedEmbedder(model_name=model_name, device=device, batch_size=batch_size)
    if not be.available:
        print('BatchedEmbedder not available (model failed to load). Aborting.')
        return

    # probe dim
    sample = be.embed(['hello world'])
    dim = sample.shape[1]
    print(f'Embedding dim detected: {dim}')

    s = FaissStore(index_path='corpus/bench_bge.index', meta_path='corpus/bench_bge_meta.json', dim=dim, batched_embedder=be)

    docs = make_docs(n)

    t0 = time.time()
    ids = s.upsert(docs, batch_size=upsert_batch_size)
    t_upsert = time.time() - t0
    print(f'Upsert {n} docs: {t_upsert:.3f}s ({t_upsert/n*1000:.3f} ms/op)')

    q = be.embed(['sample text 1'])[0]
    trials = 100
    t0 = time.time()
    for _ in range(trials):
        _ = s.search(q, top_k=5)
    t_search = time.time() - t0
    print(f'{trials} searches: {t_search:.3f}s ({t_search/trials*1000:.3f} ms/search)')

    del_ids = [f'doc_{i}' for i in range(0, n, 10)]
    t0 = time.time()
    s.delete(del_ids)
    t_delete = time.time() - t0
    print(f'Delete {len(del_ids)} ids: {t_delete:.3f}s ({t_delete/len(del_ids)*1000:.3f} ms/op)')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--n', type=int, default=2000)
    p.add_argument('--model', type=str, default='BAAI/bge-m3')
    p.add_argument('--batch_size', type=int, default=32)
    p.add_argument('--device', type=str, default=None)
    p.add_argument('--upsert-batch', type=int, default=4096)
    args = p.parse_args()
    run(n=args.n, model_name=args.model, batch_size=args.batch_size, device=args.device, upsert_batch_size=args.upsert_batch)
