"""軽量ベクタストア抽象と FAISS ベースの簡易実装（MVP）

この実装はテスト向けにデフォルトで軽量な埋め込み関数を使用します。
実運用では BGE 等の本格的な埋め込み関数を渡してください。
"""
from typing import List, Dict, Optional, Callable
import concurrent.futures
import os
import json
import numpy as np
import faiss
import uuid


class EmbedStore:
    """抽象インタフェース"""
    def upsert(self, documents: List[Dict], batch_size: Optional[int] = None) -> List[str]:
        raise NotImplementedError()

    def delete(self, ids: List[str]) -> None:
        raise NotImplementedError()

    def search(self, query_vector: np.ndarray, top_k: int = 5, filters: dict = None) -> List[Dict]:
        raise NotImplementedError()


def _simple_hash_embed(text: str, dim: int = 8) -> np.ndarray:
    # Deterministic lightweight embed for tests (not semantic)
    import hashlib
    h = hashlib.md5(text.encode()).digest()
    vals = np.frombuffer(h, dtype=np.uint8).astype('float32')[:dim]
    v = vals / (np.linalg.norm(vals) + 1e-6)
    return v.astype('float32')


class FaissStore(EmbedStore):
    def __init__(self, index_path: str = None, meta_path: str = None, embed_fn: Optional[Callable[[str], np.ndarray]] = None, dim: int = 8, embed_workers: Optional[int] = None, batched_embedder: Optional[object] = None):
        self.dim = dim
        self.embed_fn = embed_fn or (lambda t: _simple_hash_embed(t, dim=self.dim))
        self.embed_workers = embed_workers
        # optional batched embedder (e.g., src.rag.embedding_backend.BatchedEmbedder)
        self.batched_embedder = batched_embedder
        self.index_path = index_path or os.path.join('corpus', 'embed_store.index')
        self.meta_path = meta_path or os.path.join('corpus', 'embed_store_meta.json')
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)

        # initialize faiss index with ID map for efficient upsert/delete
        try:
            if os.path.exists(self.index_path):
                self.index = faiss.read_index(self.index_path)
            else:
                base = faiss.IndexFlatIP(self.dim)
                self.index = faiss.IndexIDMap(base)
        except Exception:
            base = faiss.IndexFlatIP(self.dim)
            self.index = faiss.IndexIDMap(base)

        # load meta
        if os.path.exists(self.meta_path):
            try:
                with open(self.meta_path, 'r', encoding='utf-8') as f:
                    self.meta = json.load(f)
            except Exception:
                self.meta = []
        else:
            self.meta = []

        # mapping from string id -> faiss int64 id
        self._id_to_faiss = {}
        self._next_faiss_id = 1
        # reverse mapping faiss id -> meta entry
        self._faiss_to_meta: Dict[int, Dict] = {}

        # rebuild id mapping if meta file contains faiss_id entries
        for m in self.meta:
            if 'faiss_id' in m:
                fid = int(m['faiss_id'])
                self._id_to_faiss[m['id']] = fid
                self._faiss_to_meta[fid] = m
                if fid >= self._next_faiss_id:
                    self._next_faiss_id = fid + 1

    def _save(self):
        try:
            faiss.write_index(self.index, self.index_path)
        except Exception:
            pass
        try:
            # ensure faiss_id is saved alongside meta
            meta_to_save = []
            for m in self.meta:
                mm = dict(m)
                if mm.get('id') in self._id_to_faiss:
                    mm['faiss_id'] = int(self._id_to_faiss[mm.get('id')])
                # ensure meta in memory carries faiss_id
                if 'faiss_id' not in m and mm.get('id') in self._id_to_faiss:
                    m['faiss_id'] = int(self._id_to_faiss[mm.get('id')])
                meta_to_save.append(mm)
            with open(self.meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta_to_save, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def upsert(self, documents: List[Dict], batch_size: Optional[int] = None) -> List[str]:
        ids = []

        # prepare arrays for batch add
        to_add_vectors = []
        to_add_ids = []

        texts = []
        vids = []
        metas_in = []
        for doc in documents:
            text = doc.get('text') or doc.get('content') or ''
            vid = doc.get('id') or str(uuid.uuid4())
            texts.append(text)
            vids.append(vid)
            metas_in.append({**doc, 'id': vid})
            meta = {**doc}
            meta['id'] = vid

            # determine faiss id
            if vid in self._id_to_faiss:
                faiss_id = self._id_to_faiss[vid]
                # remove existing vector with this id
                try:
                    self.index.remove_ids(np.array([faiss_id], dtype='int64'))
                except Exception:
                    # ignore if remove not supported or id not present
                    pass
            else:
                faiss_id = self._next_faiss_id
                self._next_faiss_id += 1
                self._id_to_faiss[vid] = faiss_id

            # update or append meta, and record faiss_id on meta
            meta['faiss_id'] = faiss_id
            found = False
            for i, m in enumerate(self.meta):
                if m.get('id') == vid:
                    self.meta[i] = meta
                    found = True
                    break
            if not found:
                self.meta.append(meta)

            # update reverse mapping
            self._faiss_to_meta[int(faiss_id)] = meta

            # defer embedding until after mapping faiss ids and metas
            to_add_ids.append(faiss_id)
            ids.append(vid)

        # add with ids (support chunked add to reduce faiss call overhead)
        # compute embeddings for texts in batch (vectorized embed if available, else parallel map)
        to_add_vectors = []
        try:
            # prefer explicit batched embedder if provided and available
            if getattr(self, 'batched_embedder', None) is not None and getattr(self.batched_embedder, 'available', False):
                batch_embs = self.batched_embedder.embed(texts)
            else:
                # try calling embed_fn on list (vectorized)
                batch_embs = self.embed_fn(texts)  # type: ignore

            if isinstance(batch_embs, list) or isinstance(batch_embs, np.ndarray):
                to_add_vectors = [np.asarray(v, dtype='float32') for v in batch_embs]
            else:
                # unexpected type, fall back
                raise Exception('batch embed returned unexpected type')
        except Exception:
            # fallback: parallel map
            workers = self.embed_workers or min(32, (os.cpu_count() or 1) + 4)
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
                futures = [ex.submit(self.embed_fn, t) for t in texts]
                for f in concurrent.futures.as_completed(futures):
                    to_add_vectors.append(np.asarray(f.result(), dtype='float32'))

        if to_add_vectors:
            arr = np.array(to_add_vectors, dtype='float32')
            id_arr = np.array(to_add_ids, dtype='int64')
            try:
                if batch_size and batch_size > 0:
                    # add in chunks
                    for i in range(0, len(arr), batch_size):
                        chunk_arr = arr[i:i+batch_size]
                        chunk_ids = id_arr[i:i+batch_size]
                        self.index.add_with_ids(chunk_arr, chunk_ids)
                else:
                    # single call
                    self.index.add_with_ids(arr, id_arr)
            except Exception:
                # fall back to rebuilding if necessary
                vectors = [self.embed_fn(m.get('text') or m.get('content') or '') for m in self.meta]
                self.index = faiss.IndexIDMap(faiss.IndexFlatIP(self.dim))
                if vectors:
                    self.index.add_with_ids(np.array(vectors, dtype='float32'), np.array(list(self._id_to_faiss.values()), dtype='int64'))

        self._save()
        return ids

    def delete(self, ids: List[str]) -> None:
        # remove ids from meta and from faiss index using stored faiss ids
        to_remove = []
        for doc_id in ids:
            if doc_id in self._id_to_faiss:
                fid = int(self._id_to_faiss.pop(doc_id))
                to_remove.append(fid)
                if fid in self._faiss_to_meta:
                    self._faiss_to_meta.pop(fid, None)

        # filter meta
        self.meta = [m for m in self.meta if m.get('id') not in ids]

        if to_remove:
            try:
                self.index.remove_ids(np.array(to_remove, dtype='int64'))
            except Exception:
                # fallback: rebuild entire index
                vectors = [self.embed_fn(m.get('text') or m.get('content') or '') for m in self.meta]
                self.index = faiss.IndexIDMap(faiss.IndexFlatIP(self.dim))
                if vectors:
                    # assign new sequential faiss ids
                    id_list = []
                    for m in self.meta:
                        if m.get('id') not in self._id_to_faiss:
                            fid = self._next_faiss_id
                            self._next_faiss_id += 1
                            self._id_to_faiss[m.get('id')] = fid
                            m['faiss_id'] = fid
                        id_list.append(int(self._id_to_faiss[m.get('id')]))
                        # rebuild reverse mapping
                        self._faiss_to_meta[int(self._id_to_faiss[m.get('id')])] = m
                    self.index.add_with_ids(np.array(vectors, dtype='float32'), np.array(id_list, dtype='int64'))

        self._save()

    def search(self, query_vector: np.ndarray, top_k: int = 5, filters: dict = None) -> List[Dict]:
        if self.index.ntotal == 0:
            return []

        # when filters are provided, search a larger candidate set and then apply metadata filters
        candidate_k = top_k * 5 if filters else top_k
        candidate_k = min(int(self.index.ntotal), max(1, int(candidate_k)))

        D, I = self.index.search(np.array([query_vector], dtype='float32'), candidate_k)
        results = []

        def meta_matches(meta_entry: dict, filters: dict) -> bool:
            if not filters:
                return True
            for k, v in (filters.items() if isinstance(filters, dict) else []):
                if k not in meta_entry:
                    return False
                mv = meta_entry.get(k)
                # filter value is a collection
                if isinstance(v, (list, tuple, set)):
                    # meta value is also collection -> check intersection
                    if isinstance(mv, (list, tuple, set)):
                        if not any(item in mv for item in v):
                            return False
                    else:
                        # meta scalar -> check membership in filter list
                        if mv not in v:
                            return False
                else:
                    # filter value is scalar
                    if isinstance(mv, (list, tuple, set)):
                        if v not in mv:
                            return False
                    else:
                        if mv != v:
                            return False
            return True

        for score, idx in zip(D[0], I[0]):
            # idx here is the faiss id (int) when using IndexIDMap
            fid = int(idx)
            if fid not in self._faiss_to_meta:
                continue
            entry = dict(self._faiss_to_meta[fid])
            entry['score'] = float(score)
            if filters:
                if not meta_matches(entry, filters):
                    continue
            results.append(entry)
            if len(results) >= top_k:
                break

        return results
