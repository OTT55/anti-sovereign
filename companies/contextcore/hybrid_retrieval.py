"""Hybrid retrieval — Phase 6 (§3-4 of SCALING-RESEARCH.md), built for real.

BM25 (sparse, exact-term) + pgvector dense embeddings (semantic), fused with
Reciprocal Rank Fusion, then reranked with a cross-encoder. Each rung is
independently optional and fails down to the one below it rather than
breaking the app — same honest-degradation convention as the rest of
ContextCore (generate_answer(), extract_entities_relationships(), etc.):

  hybrid + rerank  ->  hybrid (no rerank)  ->  sparse-only (no dense)  ->  legacy TF-IDF

Dense retrieval needs two real external things: an API key for embeddings
(OPENROUTER_API_KEY, preferred — already used elsewhere in this ecosystem —
or VOYAGE_API_KEY as a fallback) and a reachable Postgres+pgvector instance
(DATABASE_URL, default matches the docker-compose service this company
ships). Without either, ingest and retrieval both still work — they just
stay on the sparse/BM25 rung, exactly like every other optional layer in
this app.
"""
import os
import re

TOP_K = 4
EMBED_DIM = 512  # both providers below are asked to truncate/output this dimension
OPENROUTER_EMBED_MODEL = "openai/text-embedding-3-small"  # via OpenRouter's OpenAI-compatible /embeddings endpoint
VOYAGE_EMBED_MODEL = "voyage-4-lite"
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"

STOPWORDS = set(
    "the a an and or of to in on for with is are was were be been being this that "
    "these those it its as at by from into out over under then than so such but if "
    "how what when where who whom which why do does did done has have had not no".split()
)


def tokenize(text):
    """Duplicated from app.py's tokenize() rather than imported, to avoid a
    circular import (app.py imports this module for hybrid_retrieve())."""
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1 and t not in STOPWORDS]


# --------------------------------------------------------------------------
# Sparse: BM25 (formalizes the TF-IDF-equivalent scoring per SCALING-RESEARCH §4)
# --------------------------------------------------------------------------

def bm25_rank(question, chunk_texts):
    from rank_bm25 import BM25Okapi

    tokenized = [tokenize(t) for t in chunk_texts]
    if not any(tokenized):
        return []
    bm25 = BM25Okapi(tokenized)
    scores = bm25.get_scores(tokenize(question))
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    return [(i, float(s)) for i, s in ranked if s > 0]


# --------------------------------------------------------------------------
# Fusion: Reciprocal Rank Fusion (SCALING-RESEARCH §3.4) — combines by rank
# position, not raw score, since BM25 (0-15ish) and cosine similarity
# (0.6-0.95ish) live on incomparable scales.
# --------------------------------------------------------------------------

def reciprocal_rank_fusion(rankings, k=60):
    scores = {}
    for ranking in rankings:
        for rank, (item, _score) in enumerate(ranking):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)


# --------------------------------------------------------------------------
# Dense: Voyage embeddings + pgvector. Both optional; graceful skip.
# --------------------------------------------------------------------------

def _raw_pg_connect():
    import psycopg

    dsn = os.environ.get("DATABASE_URL", "postgresql://contextcore:contextcore@localhost:5432/contextcore")
    return psycopg.connect(dsn, autocommit=True)


def get_pg_conn():
    """For actual vector operations (store/search) — register_vector() needs
    the `vector` type to already exist, which init_pgvector_schema() (using
    the raw connection below, deliberately not this function) guarantees by
    the time anything calls this."""
    from pgvector.psycopg import register_vector

    conn = _raw_pg_connect()
    register_vector(conn)
    return conn


def init_pgvector_schema():
    """Idempotent. Called at app startup — a no-op (raises, caught by the
    caller) if Postgres isn't reachable, exactly like init_db() for SQLite
    is unconditional because SQLite has no such failure mode. Uses the raw
    connection, not get_pg_conn(): register_vector() would fail here since
    the `vector` type doesn't exist until the CREATE EXTENSION below runs."""
    conn = _raw_pg_connect()
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.execute(
        f"""CREATE TABLE IF NOT EXISTS chunk_embeddings (
            chunk_id INTEGER PRIMARY KEY,
            doc_id   TEXT NOT NULL,
            embedding vector({EMBED_DIM})
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS chunk_embeddings_hnsw "
        "ON chunk_embeddings USING hnsw (embedding vector_cosine_ops)"
    )
    conn.close()


def _embed_openrouter(texts, api_key):
    import requests

    resp = requests.post(
        "https://openrouter.ai/api/v1/embeddings",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": OPENROUTER_EMBED_MODEL, "input": texts, "dimensions": EMBED_DIM},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    data.sort(key=lambda d: d["index"])
    return [d["embedding"] for d in data]


def _embed_voyage(texts, input_type, api_key):
    import voyageai

    client = voyageai.Client(api_key=api_key)
    result = client.embed(texts, model=VOYAGE_EMBED_MODEL, input_type=input_type, output_dimension=EMBED_DIM)
    return result.embeddings


def embed_texts(texts, input_type):
    """input_type is 'document' (ingest time) or 'query' (ask time) — only
    Voyage's API uses this (asymmetric instruction tuning); OpenRouter's
    OpenAI-compatible endpoint ignores it. Tries OPENROUTER_API_KEY first
    (already part of this ecosystem's toolkit elsewhere — see Cinematic
    OTT), falling back to VOYAGE_API_KEY if OpenRouter isn't configured or
    its call fails and a Voyage key also exists. Returns (vectors, note)."""
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    voyage_key = os.environ.get("VOYAGE_API_KEY")
    if not openrouter_key and not voyage_key:
        return None, "No OPENROUTER_API_KEY or VOYAGE_API_KEY set — dense embedding skipped."

    if openrouter_key:
        try:
            return _embed_openrouter(texts, openrouter_key), None
        except Exception as e:
            if not voyage_key:
                return None, f"OpenRouter embedding call failed ({type(e).__name__}: {e})."
            # fall through to Voyage as a backup

    try:
        return _embed_voyage(texts, input_type, voyage_key), None
    except Exception as e:
        return None, f"Voyage embedding call failed ({type(e).__name__}: {e})."


def store_chunk_embeddings(doc_id, id_text_pairs):
    """Best-effort: embed each new chunk once at ingest time and upsert into
    pgvector, so query time never re-embeds anything (the actual fix for the
    O(N)-per-query problem in SCALING-RESEARCH §3.1). Silent no-op (with a
    note) if Voyage or Postgres aren't available — ingest must never fail
    because of this optional layer."""
    if not id_text_pairs:
        return 0, None
    vectors, note = embed_texts([t for _, t in id_text_pairs], input_type="document")
    if vectors is None:
        return 0, note
    try:
        conn = get_pg_conn()
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO chunk_embeddings (chunk_id, doc_id, embedding) VALUES (%s, %s, %s) "
                "ON CONFLICT (chunk_id) DO UPDATE SET embedding = EXCLUDED.embedding",
                [(cid, doc_id, vec) for (cid, _), vec in zip(id_text_pairs, vectors)],
            )
        conn.close()
        return len(vectors), None
    except Exception as e:
        return 0, f"Postgres write failed ({type(e).__name__}: {e}) — chunks indexed for sparse search only."


def dense_search_for_chunks(question, chunk_ids):
    """Cosine search restricted to a specific set of chunk_ids (one document
    or one collection's worth) — an explicit ID filter rather than a
    whole-corpus ANN search, which is exactly right at this corpus size
    (brute-force-equivalent; see SCALING-RESEARCH §3.3 on when HNSW's
    approximate search actually starts mattering)."""
    if not chunk_ids:
        return None, None
    vectors, note = embed_texts([question], input_type="query")
    if vectors is None:
        return None, note
    q_emb = vectors[0]
    try:
        conn = get_pg_conn()
        placeholders = ",".join("%s" for _ in chunk_ids)
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT chunk_id, 1 - (embedding <=> %s) AS score FROM chunk_embeddings "
                f"WHERE chunk_id IN ({placeholders}) ORDER BY embedding <=> %s LIMIT %s",
                [q_emb, *chunk_ids, q_emb, max(len(chunk_ids), TOP_K * 3)],
            )
            rows = cur.fetchall()
        conn.close()
        return [(r[0], float(r[1])) for r in rows], None
    except Exception as e:
        return None, f"Postgres query failed ({type(e).__name__}: {e}) — using sparse (BM25) only."


# --------------------------------------------------------------------------
# Reranking: BGE-reranker-v2-m3, self-hosted (Apache 2.0), no API key, per
# SCALING-RESEARCH §4's recommendation to skip the hosted-API cost. Loaded
# once and cached at module level — the ~1-2GB weights download happens on
# first use, cached by HuggingFace afterward.
# --------------------------------------------------------------------------

_reranker = None


def get_reranker():
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder(RERANK_MODEL)
    return _reranker


def rerank_candidates(question, candidates):
    """candidates: [(local_index, text), ...]. Returns ([(local_index, score)], note).
    Scores are sigmoid'd into [0,1] (bge-reranker-v2-m3 outputs a raw logit,
    not a bounded probability by default) so they land on the same scale
    app.py's assess_confidence() was calibrated against for TF-IDF cosine
    similarity — a genuine relevance probability, not raw model output."""
    if not candidates:
        return [], None
    try:
        import torch
        model = get_reranker()
        pairs = [[question, text] for _, text in candidates]
        raw_scores = model.predict(pairs)
        scores = torch.sigmoid(torch.tensor(raw_scores)).tolist()
    except Exception as e:
        return None, f"Reranking failed ({type(e).__name__}: {e}) — using pre-rerank order."
    scored = sorted(zip((i for i, _ in candidates), scores), key=lambda x: x[1], reverse=True)
    return [(i, float(s)) for i, s in scored], None


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def hybrid_retrieve(question, chunk_ids, chunk_texts, k=TOP_K):
    """Returns (hits, mode, note). hits is [(local_index, score), ...],
    shaped exactly like app.py's retrieve() so it's a drop-in replacement —
    everything downstream (confidence, citations, generation) is unchanged.

    mode is one of: "hybrid+rerank", "hybrid", "sparse-only", "tfidf-fallback".
    note explains any degradation, same convention as generate_answer().
    """
    try:
        bm25_ranked = bm25_rank(question, chunk_texts)
    except Exception as e:
        return None, "tfidf-fallback", f"BM25 unavailable ({type(e).__name__}: {e}) — falling back to legacy TF-IDF."

    dense_ranked, dense_note = dense_search_for_chunks(question, chunk_ids)
    if dense_ranked is None:
        return bm25_ranked[:k], "sparse-only", dense_note

    id_to_local = {cid: i for i, cid in enumerate(chunk_ids)}
    dense_local = [(id_to_local[cid], score) for cid, score in dense_ranked if cid in id_to_local]

    fused = reciprocal_rank_fusion([bm25_ranked, dense_local])
    candidates = fused[:max(k * 3, 20)]

    reranked, rerank_note = rerank_candidates(question, [(i, chunk_texts[i]) for i, _ in candidates])
    if reranked is None:
        return candidates[:k], "hybrid", rerank_note
    return reranked[:k], "hybrid+rerank", None
