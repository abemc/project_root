"""RAG-related utilities: TF-IDF keyword extraction, simple summarization, optional spaCy NER."""
from typing import List, Dict, Optional
import re
from collections import Counter, defaultdict
import math


DEFAULT_STOPWORDS = set([
    "the", "and", "for", "with", "this", "that",
    "に", "の", "を", "は", "が", "で", "です", "ます"
])


def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    # split on non-word, keep unicode words of length>=2
    toks = re.findall(r"\w{2,}", text, flags=re.UNICODE)
    return [t.lower() for t in toks if len(t) >= 2]


def extract_keywords_tfidf(docs: List[Dict], top_k: int = 10, stopwords: Optional[set] = None) -> List[str]:
    stop = stopwords or DEFAULT_STOPWORDS
    # document frequency and term frequencies
    df = defaultdict(int)
    tfs = []
    for d in docs:
        text = d.get("text") or d.get("result") or ""
        toks = _tokenize(text)
        toks = [t for t in toks if t not in stop]
        tf = Counter(toks)
        tfs.append(tf)
        for term in set(tf.keys()):
            df[term] += 1

    N = max(1, len(docs))
    idf = {term: math.log((N + 1) / (dfcnt + 1)) + 1.0 for term, dfcnt in df.items()} if df else {}

    # aggregate tf-idf scores across docs
    scores = defaultdict(float)
    for tf in tfs:
        for term, cnt in tf.items():
            if term in idf:
                scores[term] += cnt * idf[term]

    # sort
    items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [term for term, _ in items[:top_k]]


def summarize_docs(docs: List[Dict], max_sentences: int = 3, keywords: Optional[List[str]] = None) -> str:
    # simple extractive summarizer: score sentences by keyword overlap and term frequency
    texts = []
    for d in docs:
        if isinstance(d, dict):
            texts.append(d.get("text") or d.get("result") or "")
        else:
            texts.append(str(d))
    full = "\n".join(t for t in texts if t)
    if not full:
        return ""

    # naive sentence split including Japanese punctuation
    sents = re.split(r'(?<=。|\.|\?|!|\n)', full)
    sents = [s.strip() for s in sents if s.strip()]

    if not sents:
        return full[:200]

    # prepare keyword set
    kwset = set([k.lower() for k in (keywords or [])])

    # base term frequency
    tf = Counter(_tokenize(full))

    def score_sent(s: str) -> float:
        toks = _tokenize(s)
        sc = 0.0
        for t in toks:
            sc += tf.get(t, 0)
            if t in kwset:
                sc += 2.0
        return sc

    scored = [(score_sent(s), i, s) for i, s in enumerate(sents)]
    scored.sort(reverse=True)
    top = [s for _, _, s in scored[:max_sentences]]
    return "\n".join(top)


def extract_entities_spacy(docs: List[Dict], top_k: int = 5) -> List[str]:
    try:
        import spacy
        # try small multilingual model if available
        try:
            nlp = spacy.load("xx_ent_wiki_sm")
        except Exception:
            nlp = spacy.blank("xx")

        ents = Counter()
        for d in docs:
            text = d.get("text") or d.get("result") or ""
            doc = nlp(text)
            for ent in doc.ents:
                ents[ent.text.strip()] += 1
        return [e for e, _ in ents.most_common(top_k)]
    except Exception:
        return []
