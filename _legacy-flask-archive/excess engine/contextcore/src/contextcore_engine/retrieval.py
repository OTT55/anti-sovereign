"""TF-IDF vector index + cosine retrieval. Pure Python, no external ML dependency."""

import math
from collections import Counter

from .chunking import tokenize

DEFAULT_TOP_K = 4


def build_index(chunks):
    """Return (chunk_vectors, idf). Vectors are normalized tf-idf dicts."""
    tokenized = [tokenize(c) for c in chunks]
    df = Counter()
    for toks in tokenized:
        for term in set(toks):
            df[term] += 1
    n = len(chunks)
    idf = {term: math.log((n + 1) / (dfi + 1)) + 1 for term, dfi in df.items()}
    vectors = []
    for toks in tokenized:
        tf = Counter(toks)
        vec = {term: (count / len(toks)) * idf[term] for term, count in tf.items()} if toks else {}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        vectors.append({t: v / norm for t, v in vec.items()})
    return vectors, idf


def query_vector(question, idf):
    toks = tokenize(question)
    if not toks:
        return {}
    tf = Counter(toks)
    vec = {term: (count / len(toks)) * idf.get(term, math.log(2) + 1) for term, count in tf.items()}
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {t: v / norm for t, v in vec.items()}


def cosine(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(t, 0.0) for t, v in a.items())


def retrieve(question, vectors, idf, k=DEFAULT_TOP_K):
    q = query_vector(question, idf)
    scored = [(cosine(q, vec), i) for i, vec in enumerate(vectors)]
    scored.sort(reverse=True)
    return [(i, score) for score, i in scored[:k] if score > 0]


class TFIDFIndex:
    """A searchable index over a fixed list of chunks."""

    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.vectors, self.idf = build_index(self.chunks)

    def search(self, question, k=DEFAULT_TOP_K):
        """Return [(chunk_index, score), ...] sorted by relevance, highest first."""
        return retrieve(question, self.vectors, self.idf, k=k)
