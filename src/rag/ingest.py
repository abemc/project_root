"""Ingest pipeline: chunking, normalization, embedding and upsert into EmbedStore

Provides simple functions to prepare documents and push them into an EmbedStore (FaissStore).
"""
from typing import List, Dict, Optional
import re
from datetime import datetime

from .embed_store import FaissStore


def normalize_text(text: str) -> str:
    text = text.replace('\r', ' ').replace('\n', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    words = text.split()
    if len(words) <= chunk_size:
        return [text]
    chunks = []
    i = 0
    while i < len(words):
        chunk = ' '.join(words[i:i+chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


def ingest_documents(
    documents: List[Dict],
    store: Optional[FaissStore] = None,
    chunk_size: int = 500,
    overlap: int = 50
) -> List[str]:
    """Ingest a list of documents into the provided FaissStore.

    documents: list of {"id":..., "text":..., ...}
    Returns list of upserted ids
    """
    if store is None:
        store = FaissStore()

    to_upsert = []
    for doc in documents:
        doc_id = doc.get('id')
        text = normalize_text(doc.get('text') or doc.get('content') or '')
        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        for ci, chunk in enumerate(chunks):
            meta = dict(doc)
            meta['text'] = chunk
            meta['chunk_index'] = ci
            # standardized metadata fields
            meta['ingested_at'] = datetime.now().isoformat()
            if 'created_at' not in meta:
                meta['created_at'] = meta['ingested_at']
            if 'domain' not in meta:
                meta['domain'] = doc.get('domain') or 'general'
            if 'tags' not in meta:
                # allow older 'tag' field
                if 'tag' in meta:
                    meta['tags'] = [meta.pop('tag')]
                else:
                    meta['tags'] = []
            # create unique id for chunk
            if doc_id:
                meta['id'] = f"{doc_id}__chunk__{ci}"
            to_upsert.append(meta)

    # perform upsert in batches to leverage chunked add
    ids = []
    batch_size = 1024
    for i in range(0, len(to_upsert), batch_size):
        batch = to_upsert[i:i+batch_size]
        ids.extend(store.upsert(batch, batch_size=256))
    return ids


def ingest_file_path(path: str, store: Optional[FaissStore] = None):
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    text = p.read_text(encoding='utf-8')
    return ingest_documents([{"id": p.name, "text": text}], store=store)
