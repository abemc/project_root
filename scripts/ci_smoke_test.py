"""CI smoke test: register -> query -> delete -> query -> persist -> load"""
from pathlib import Path
import json
import time
from src.rag.chroma_store import ChromaStore
from src.rag.faiss_store import FaissStore
from sentence_transformers import SentenceTransformer

MODEL='intfloat/multilingual-e5-small'

class EF:
    def __init__(self):
        self.m=SentenceTransformer(MODEL)
    def embed(self, texts):
        return self.m.encode(texts, show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=False).tolist()


def run():
    out = Path('results')
    out.mkdir(exist_ok=True)
    chroma = ChromaStore(path='corpus/chroma_db', collection_name='rag_knowledge_base')
    faiss = FaissStore(index_path='corpus/faiss_ci.index', metadata_db='corpus/faiss_ci.db', embedding_fn=EF())

    # small dataset
    docs = [
        ('doc1', '太閤記の説明', {'source':'doc1'}),
        ('doc2', '秀吉の生涯について', {'source':'doc2'}),
        ('doc3', '聚楽桃山の記述', {'source':'doc3'})
    ]
    ids = [d[0] for d in docs]
    texts = [d[1] for d in docs]
    metas = [d[2] for d in docs]

    # add to both stores
    chroma.add_documents(ids, texts, metas)
    faiss.add_documents(ids, texts, metas)

    # query
    c = chroma.query(['秀吉'], n_results=2)
    f = faiss.query(['秀吉'], n_results=2)

    result = {'chroma': c, 'faiss': f}
    with (out/'ci_smoke_before.json').open('w', encoding='utf-8') as fjson:
        json.dump(result, fjson, ensure_ascii=False, indent=2)

    # delete doc2
    chroma.delete(['doc2'])
    faiss.delete(['doc2'])

    c2 = chroma.query(['秀吉'], n_results=2)
    f2 = faiss.query(['秀吉'], n_results=2)
    result2 = {'chroma_after_delete': c2, 'faiss_after_delete': f2}
    with (out/'ci_smoke_after.json').open('w', encoding='utf-8') as fjson:
        json.dump(result2, fjson, ensure_ascii=False, indent=2)

    # persist and reload faiss
    faiss.persist()
    # instantiate fresh
    faiss2 = FaissStore(index_path='corpus/faiss_ci.index', metadata_db='corpus/faiss_ci.db', embedding_fn=EF())
    f3 = faiss2.query(['秀吉'], n_results=2)
    with (out/'ci_smoke_reload.json').open('w', encoding='utf-8') as fjson:
        json.dump({'faiss_reload': f3}, fjson, ensure_ascii=False, indent=2)

    print('CI smoke test complete. Results in results/ ci_smoke_*.json')

if __name__ == '__main__':
    run()
