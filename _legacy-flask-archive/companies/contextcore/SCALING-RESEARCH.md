# ContextCore at scale — research notes

**Status: §5's Phase 1-3 (dense retrieval, hybrid fusion, reranking) are built — see
the per-phase notes in §5 for exactly what's live vs. pending. Phases 4-5 (multi-domain
ingestion, collection-level scale-out) remain research only.** The original MVP retrieval
path (pure-Python TF-IDF) is untouched and still runs — hybrid retrieval is additive, with
a fallback chain down to it if anything in the new stack is unavailable (see `app.py`'s
`hybrid_retrieve()` in `hybrid_retrieval.py`).

**Honest caveat on why this got built ahead of actual scale need**: the founder was asked
whether the minimal slice (embeddings + brute-force cosine, no new infrastructure) or the
full researched stack made more sense at ContextCore's current ~24-chunk corpus size, and
explicitly chose the full stack. That's a real, deliberate choice, not a default — the
premature-infrastructure risk this document warned about going in is still real; it's just
been knowingly accepted rather than avoided. Worth remembering if this corpus doesn't grow
much further: the honest read from the numbers in §3 hasn't changed.

The prompt for this doc was: don't limit this to films, this is going to be big, cover
the math, the tools, and what data we need, and how to scale. That's the order this
document follows.

---

## 1. Reframe: not a film tool, a domain-intelligence refinery

The `distribution-intelligence` collection proved the mechanism: real documents in,
pooled retrieval, cited generation out. Nothing about that mechanism is film-specific.
The **collection** primitive (a named, growable corpus, queried as one pool) generalizes
to any domain where you'd otherwise write a bespoke rules engine over curated facts.
Two other Sovereign Stack ideas already on the table are really the same shape:

| Collection | Domain | What it replaces |
|---|---|---|
| `distribution-intelligence` | Film release strategy | (built) — was LaunchWindow's rules engine |
| `compliance-corpus` | Regulatory / jurisdiction rules | Could deepen **Clearpath**'s hand-coded rules engine the same way |
| `capital-markets` | Production financing, deal comps | Feeds the "Production Finance Platform" idea from earlier |
| `talent-signal` | Crew/cast track record | Feeds "Talent Signal Layer" — but see §2, this one has no clean external dataset |

The architecture question below is the same regardless of which collection you fill in
first — this is genuinely a platform decision, not a per-domain one.

---

## 2. What data we need

Real, checked sources — not a wishlist. Each entry below was verified this session
(pricing/terms current as of **2026-07**), and flagged honestly where the license is a
problem for a commercial product, because two of the obvious film sources have real
legal landmines.

### Entertainment / Film

| Source | What it gives you | License reality |
|---|---|---|
| **[TMDB API](https://www.themoviedb.org/api-terms-of-use)** | Rich metadata, cast/crew, images | **Free tier explicitly prohibits use "in connection with machine learning (ML) or artificial intelligence (AI) based applications."** This blocks TMDB as a free source for a RAG product outright. Commercial license is $149/mo under $1M revenue, custom above — and you'd still need to check whether that license lifts the AI restriction before relying on it. |
| **[IMDb non-commercial datasets](https://www.imdb.com/interfaces/)** | Title/rating/cast bulk TSVs | Free for **personal, non-commercial** use only; explicitly bars using the data to build another movie-information product, bars scraping the site itself (the bulk files are the sanctioned path), and requires attribution. The moment this ships as part of a company's product — monetized or not — that's commercial use and needs IMDb's separate commercial license via [developer.imdb.com](https://developer.imdb.com/). |
| **Wikipedia / Wikidata film infoboxes** | Release dates, box office, cast, genre — structured, and years of it | **CC-BY-SA — genuinely free for commercial and AI use with attribution.** This is the clean, unrestricted option and should probably be the first real ingestion source, ahead of either of the two above. |
| **Common Crawl** | Raw web text, includes trade-press-adjacent pages | Free, no usage restriction on the crawl itself, but needs heavy filtering/dedup before it's useful — not a quick win. |

**The practical read:** don't build the entertainment collection on TMDB or IMDb without
paying for the commercial license. Wikipedia/Wikidata is the honest free path and is
large enough to meaningfully deepen the 6 seed documents.

### Legal / Compliance (feeds Clearpath)

| Source | What it gives you | License reality |
|---|---|---|
| **[CourtListener / RECAP](https://www.courtlistener.com/help/api/bulk-data/)** (Free Law Project, 501(c)(3)) | 9M+ case law decisions, PACER docket data via RECAP, judge bios | Free and open; **as of May 2026 the free API rate limit dropped and higher tiers require Free Law Project membership** — still has full bulk-data downloads for case law and courts. |
| **[SEC EDGAR](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)** | Every SEC filing since 2001, full-text search, XBRL financials | Completely free, **no API key, no registration**, 10 req/sec, nightly bulk ZIPs (`companyfacts.zip`, `submissions.zip`). This is the cleanest, most generous free dataset of the entire list. |

### Finance (feeds "Production Finance Platform")

SEC EDGAR again (13F holdings, financial statements) is the honest starting point — no
separate finance-specific free source is as clean. Real deal-comp data (Crunchbase,
PitchBook) is paid and would be a licensing decision, not an engineering one.

### Talent / crew track record (feeds "Talent Signal Layer")

**There is no clean external dataset for this one.** Crew/cast performance and on-set
outcome data isn't published anywhere free or paid, for good reason — it's exactly the
kind of proprietary signal a platform earns by operating, not by scraping. This collection
realistically has to be built from your own FilmCrew hiring data over time (as flagged
earlier), not sourced. Worth knowing now so it's not on the near-term roadmap.

---

## 3. The math

### 3.1 Why TF-IDF (the current engine) doesn't scale semantically

The current `build_index()` does exact lexical matching: a query for "movie" scores zero
against a chunk that only says "film" or "picture" — no shared vocabulary, no match,
regardless of how relevant the passage is. That's the fundamental ceiling of sparse
lexical retrieval, and it's why the fix isn't "more TF-IDF," it's adding a **dense**
(embedding-based) retrieval path that captures meaning instead of exact words.

There's also a **compute** ceiling, separate from the semantic one: `collection_ask()`
today calls `build_index(texts)` **fresh, on every single request** — that's every chunk
in the collection, re-tokenized and re-vectorized, per query. At 24 chunks that's
invisible. At 1M chunks that's rebuilding a full index on every user question, which
is not viable at any real query volume. Production retrieval needs a **persistent,
incrementally-updated index** — build once when a document is ingested, query against
the standing index, update only the delta when new documents arrive.

### 3.2 Embedding vectors: the actual numbers

An embedding turns a chunk of text into a fixed-length vector of floats (e.g. 1024
numbers). Similarity between two chunks is cosine similarity between their vectors —
same math the current TF-IDF code already does (`cosine()` in `app.py`), just over dense
vectors instead of sparse ones.

**Storage per vector**, float32 (4 bytes per dimension):

```
bytes_per_vector = dimensions × 4
```

At 1024 dimensions: `1024 × 4 = 4,096 bytes ≈ 4 KB per chunk.`

**Index memory**, including the HNSW graph overhead (the graph structure that makes
search fast — see §3.3) typically adds 1.5–2× on top of raw vector storage:

```
index_memory ≈ (num_chunks × bytes_per_vector) × 1.5–2
```

| Scale | Raw vectors (1024-dim) | With HNSW overhead |
|---|---|---|
| 10K chunks (small pilot) | 40 MB | ~60–80 MB |
| 1M chunks (one good-sized collection) | 4 GB | ~6–8 GB |
| 100M chunks (all sources in §2, combined) | 400 GB | ~600–800 GB |

At 100M chunks, that overhead is the point where you either (a) use **Matryoshka
truncation** — Voyage's embeddings support truncating 1024 dims down to 256 without
re-embedding, a straight 4× storage cut in exchange for some recall loss, or (b) move to
a **quantized** index (scalar or product quantization, typically another 4–8× reduction)
, or (c) accept a managed/distributed vector store built for this scale (Pinecone).

### 3.3 Search complexity: brute force vs. HNSW

Brute-force cosine similarity (what the current TF-IDF `retrieve()` does, and what naive
dense search would also do) is **O(N)** per query — score every chunk, sort, take top-k.
Fine at N=24. At N=1M, that's a million cosine computations per question.

**HNSW** (Hierarchical Navigable Small World graphs — the indexing structure behind
pgvector, Qdrant, Pinecone) organizes vectors into a navigable graph so a query only
visits a small, relevant neighborhood instead of everything — roughly **O(log N)** query
time, at the cost of that 1.5–2× memory overhead and imperfect (but tunable, ~95–99.5%)
recall versus brute force. This is the standard, non-optional trade at any real scale.

### 3.4 Hybrid retrieval: why dense embeddings alone aren't the answer either

Dense embeddings are worse than lexical (BM25/TF-IDF) at exact terms — product codes,
proper names, statute numbers, ticker symbols — because embedding models smooth meaning
across nearby words and can blur precise tokens. The current production answer is
**hybrid search**: run BM25 and dense vector search in parallel, then merge with
**Reciprocal Rank Fusion (RRF)**, which combines by rank position rather than raw score
(BM25 scores might range 0–15, cosine similarities 0.6–0.95 — you can't just average
those, so RRF sidesteps the mismatch entirely). On a benchmark e-commerce dataset
(WANDS), hybrid reaches 0.7497 NDCG versus 0.6983 for BM25 alone and 0.6953 for dense
alone — roughly a 7% lift from combining both, not from either one being individually
better.

### 3.5 A realistic latency budget

For an interactive query (user asks a question, expects an answer in a few seconds):

```
embed the query           ~50–150 ms   (one short API call, or local model)
hybrid retrieval (ANN)    ~10–50 ms    (HNSW search, sub-linear)
rerank top candidates     ~100–300 ms  (cross-encoder over ~20–100 candidates)
Claude generation         ~1–3 s       (dominates total latency)
```

Generation is the bottleneck, not retrieval — which means the retrieval-side investments
in this document buy you *accuracy*, not speed; speed is a generation-model/streaming
question, already handled by the existing `generate_answer()` pattern.

### 3.6 Cost math at three scales

Using Voyage AI's current embedding pricing (`voyage-4-lite`, $0.02 per million tokens;
every account also gets 200M tokens free) and an estimate of ~150 tokens per 600-char
chunk:

| Scale | Tokens to embed | Embedding cost (voyage-4-lite) |
|---|---|---|
| 10K chunks | 1.5M tokens | ~$0.03 (covered by the free tier) |
| 1M chunks | 150M tokens | ~$3 (still mostly covered by the free tier on a new account) |
| 100M chunks | 15B tokens | ~$300 |

Query-time embedding cost is negligible (a question is ~20–50 tokens). Reranking, if
using Cohere's hosted API, is priced at $2 per 1,000 search units (one unit ≈ one query
against up to 100 documents) — at 1M queries/month that's roughly $2,000/month; the
self-hosted open-source alternative (BGE-reranker-v2-m3, Apache 2.0) has zero marginal
cost once you own the GPU, and reportedly matches Cohere's latency on GPU hardware.
Generation cost is whatever `claude-opus-4-8` (or a cheaper model for high-volume
queries) already costs per the existing pricing table — unchanged by anything in this
document.

---

## 4. The tools

| Layer | Recommendation | Why |
|---|---|---|
| **Embeddings** | [Voyage AI](https://embeddingcost.com/voyage) `voyage-4-lite` → `voyage-4` as quality needs grow | Cheapest credible option, 200M free tokens, Matryoshka truncation for storage control, domain-specific variants exist for law/finance (relevant given §2), and all voyage-4 models share one vector space so you can upgrade the embedding model without re-embedding everything. |
| **Vector store** | **pgvector** while under ~5M vectors; **Qdrant** if you want a managed service without adopting Postgres | pgvector (HNSW since 0.5.0) matches or beats dedicated vector DBs at ≤5M-vector scale, and it means one fewer service to run since this app already uses SQLite/relational storage. Its weak point is metadata filtering (post-filters the candidate set rather than filtering inside the graph) — Qdrant filters inside the graph traversal, which matters more once you're filtering by collection/category on a large corpus. |
| **Sparse/keyword search** | `rank_bm25` (pure Python) for now; Elasticsearch/OpenSearch only if a managed hybrid store is wanted later | Matches the codebase's existing "hand-rolled, no black-box framework" style (the current TF-IDF implementation is already pure Python) — BM25 is a small, well-understood algorithm, not a reason to adopt a new service. |
| **Fusion** | Reciprocal Rank Fusion, hand-rolled (~20 lines) | It's rank-based arithmetic, not a library dependency — same philosophy as the rest of this codebase. |
| **Reranking** | Skip initially; add **BGE-reranker-v2-m3** (self-hosted, Apache 2.0) or Cohere Rerank (hosted, $2/1K units) once query volume justifies the accuracy gain | Reranking is a real accuracy lever (recall@5 of 0.816 on a mixed text/table financial-document benchmark with a two-stage hybrid+rerank pipeline) but is the layer to add *after* hybrid retrieval is working, not before. |
| **Ingestion** | Keep the existing `ingest_document()` path; add per-source adapters (one per §2 dataset) that convert raw records into prose documents before ingesting | No new ingestion framework needed — the same function `seed_distribution.py` already calls is the entire interface. |
| **Orchestration** | Skip LangChain/LlamaIndex | The codebase's existing philosophy (hand-rolled TF-IDF, explicit chunking, explicit retrieval) is more legible and more debuggable than adopting a framework whose retrieval internals you didn't write — the actual amount of "framework" code needed here (BM25 + RRF + an embeddings API call) is small enough to own directly. |

---

## 5. How to scale — a phased path

Each phase is additive; nothing below requires ripping out what exists.

**Phase 0 (done).** Pure-Python TF-IDF, per-request index rebuild, SQLite storage,
extractive fallback. Correct architecture for a demo; the ceiling is exactly what §3.1
describes.

**Phase 1 — persistent dense retrieval. Built; Postgres live, pending an embedding key.**
`hybrid_retrieval.py` embeds each chunk once at ingest time (`store_chunk_embeddings()`,
called from `ingest_document()`) into a `pgvector`-backed `chunk_embeddings` table
(`init_pgvector_schema()`), with a real HNSW cosine index, queried by
`dense_search_for_chunks()` instead of rebuilding anything at query time — the actual
O(N)-per-query fix from §3.1 is real code now. Docker Desktop is installed and running,
`docker compose up -d` brought up `pgvector/pgvector:pg16` on port 5432, and
`init_pgvector_schema()` connected and created the real `vector(512)` column + HNSW index
— confirmed via `psql \d chunk_embeddings`, not just "the code ran." **Still pending**:
an embedding API key. `embed_texts()` tries `OPENROUTER_API_KEY` first (OpenRouter's
`/embeddings` endpoint, `openai/text-embedding-3-small` — already used elsewhere in this
ecosystem), falling back to `VOYAGE_API_KEY` (`voyage-4-lite`) if that's what's available
instead. Neither is set yet. Until one is, ingest and retrieval both correctly stay on
the sparse rung below — verified live via that exact fallback path, not yet via a real
embedding.

**Phase 2 — hybrid retrieval + fusion. Built and live (sparse leg).**
`rank_bm25.BM25Okapi` (`bm25_rank()`) replaced the ad-hoc TF-IDF-as-BM25-equivalent
framing with the real thing, and `reciprocal_rank_fusion()` is hand-rolled RRF exactly as
planned. Verified live against the real seeded corpus (`retrieval_mode: "sparse-only"` in
`/collection/<c>/ask` responses) and, separately, against a simulated dense result to
confirm the RRF-fusion code path itself is correct — the ~7% relevance lift from §3.4 only
shows up once the dense leg above is actually active, since fusion needs two real ranked
lists to fuse.

**Phase 3 — reranking. Built and live.**
`rerank_candidates()` runs `BAAI/bge-reranker-v2-m3` (self-hosted via
`sentence-transformers.CrossEncoder`, Apache 2.0, no API key) over hybrid candidates, with
scores sigmoid'd into a genuine `[0,1]` relevance probability. Verified live on this CPU-only
machine (no discrete GPU) with a real query and two real candidate passages — the model
correctly scored the on-topic passage higher. Only exercised end-to-end via
`retrieval_mode: "hybrid+rerank"` once the dense leg is active, same as Phase 2.

**Phase 4 — multi-domain ingestion.**
Build the per-source adapters for §2's real datasets (Wikipedia/Wikidata first — it's
the only entertainment source with no license problem; SEC EDGAR and CourtListener for
the legal/finance collections), running as a batch/queue-based ingestion job rather than
synchronous ingestion, since bulk sources are large enough that ingesting them inline in
a web request isn't practical.

**Phase 5 — collection-level scale-out.**
Once any single collection approaches the 1M–100M chunk range from §3.2's table,
revisit the pgvector-vs-managed-store decision per collection — a collection doesn't
have to all live on the same infrastructure, since `category` is already the sharding
key the schema uses today.

---

## Sources checked this session

- [Voyage AI pricing](https://embeddingcost.com/voyage) and [model specs](https://pecollective.com/tools/text-embedding-models-compared/)
- [pgvector vs Pinecone vs Qdrant 2026 comparison](https://www.kalviumlabs.ai/blog/vector-databases-compared-pgvector-pinecone-qdrant-weaviate/) and [benchmark data](https://vecstore.app/blog/vector-database-performance-compared)
- [IMDb non-commercial dataset terms](https://help.imdb.com/article/imdb/general-information/can-i-use-imdb-data-in-my-software/G5JTRESSHJBBHTGX) and [interfaces page](https://www.imdb.com/interfaces/)
- [TMDB API terms of use](https://www.themoviedb.org/api-terms-of-use) (note the AI/ML restriction) and [commercial pricing](https://www.themoviedb.org/api-for-business)
- [Hybrid search / RRF production guide](https://appscale.blog/en/blog/hybrid-search-and-reranking-production-rag-bm25-dense-cross-encoder-2026)
- [CourtListener bulk data](https://www.courtlistener.com/help/api/bulk-data/) and [2026 API membership change](https://free.law/2026/05/07/api-included-in-memberships/)
- [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [Cohere Rerank pricing](https://bigdataboutique.com/blog/rag-reranking-improving-retrieval-quality-with-cross-encoders) and [BGE reranker open-source alternative](https://zeroentropy.dev/articles/open-source-alternatives-to-cohere-rerank/)
