# ContextCore — Data Refineries (RAG + Collections)

**Sovereign Stack company #8 · Category: Data Refineries**

ContextCore turns documents into a queryable knowledge source, grounded in — and cited
back to — the source text. It started as single-document RAG (upload one document, ask
questions about it). It now also supports **collections**: named, persistent, growable
corpora spanning many documents, queried as one pool with the same retrieval engine. A
collection is where a **structured analysis mode** — a form instead of a text box — plugs
into that same engine, instead of being written as a separate, bespoke rules engine.

## Why this isn't NotebookLM

NotebookLM (and tools like it) is per-session, single-document Q&A: you upload a document,
ask about it, and when the session ends, so does the corpus — nothing persists or grows
across visits, and there's no way to build a durable, shared knowledge base for a domain.

ContextCore's collections are the opposite of that. A collection is a knowledge base you
build up once and keep querying — new documents get ingested into it over time, every
future question retrieves against everything ingested so far, and it's shared across
anyone using the app, not scoped to one person's one-off upload. Layered on top of that,
a collection can expose a **structured query mode**: a form UI that builds a
natural-language question and asks it against the collection, instead of requiring
users to type free text. That's a genuinely different shape of product — an accumulating
domain-intelligence corpus with purpose-built front ends — not a bigger single-document
chat box.

## Case study: Distribution Intelligence

This company folder used to also contain a second, standalone company — **LaunchWindow**,
a "release-strategy engine" that recommended distribution windows and platform strategy
for a film based on genre, budget tier, and awards intent. It worked by looking up a
hand-written Python dictionary of release-window rules and comp titles.

Looked at honestly, that dictionary lookup **was RAG already** — just implemented by hand
instead of through a real retrieval pipeline: a knowledge base (the dict), a query
(genre + budget tier + awards intent), retrieval of the relevant entries, and a generated
answer citing real evidence (comp titles). So LaunchWindow has been merged into
ContextCore as the `distribution-intelligence` **collection**:

1. The curated release-window knowledge got rewritten as six real, original prose
   documents — "Horror and the October Corridor," "Summer Tentpoles," "Awards Season
   Release Strategy," and so on (see `seed_distribution.py`). Every film, date, and
   outcome cited in them is a genuine historical fact (Halloween's Oct 25 1978 release,
   Oppenheimer's summer-awards run, Everything Everywhere All at Once's SXSW-to-wide
   platform strategy) — nothing fabricated or statistically synthesized.
2. Those six documents are ingested into the collection through the exact same
   `ingest_document()` path any other document uses.
3. The old genre/budget-tier/awards-intent form still exists, but it does exactly one
   thing now: build a natural-language question ("What is the best release window and
   distribution platform strategy for a micro-budget horror/indie film, being positioned
   for awards consideration? Cite specific real comparable releases...") and submit it to
   `/collection/distribution-intelligence/ask` — the same endpoint the free-form question
   box next to it calls. **There is no separate function that decides the answer.**
   Retrieval (TF-IDF cosine similarity across the pooled chunks) finds the relevant
   passages, and generation (Claude, or an extractive fallback with no API credit) turns
   them into prose, citing which document each part came from.

Verified live: a query for "micro-budget horror/indie, awards intent" correctly pulled
passages from three different documents (Low-Budget Distribution, Horror corridor, and
Awards Season) and cited each by title — cross-document retrieval working exactly as
designed, with zero bespoke logic determining the content of the answer.

## Real-world examples of what would extend this corpus properly

The current six documents are what's honestly buildable by hand right now: real,
verifiable facts, written as original prose. A funded, production version of this
collection would grow from real licensed or public data sources, ingested through the
same pipeline:

- **Box Office Mojo / The Numbers** — historical release-date and box-office-performance
  data going back decades; the richest source for comp-title analysis at scale.
- **MPA (Motion Picture Association) theatrical market statistics reports** — annual
  reports on release patterns, screen counts, and seasonal performance trends.
- **Comscore / Nielsen panel data** — audience demographic and streaming-performance data,
  which is what would make the "audience-targeting" side of this genuinely data-driven
  rather than heuristic.
- **Academic marketing research on release timing and seasonality** — published studies
  specifically on movie release-window economics exist in marketing and media-economics
  journals; they're citable, methodologically real evidence rather than industry folklore.
- **Trade press archives (Variety, Deadline, The Hollywood Reporter)** — for qualitative
  case studies on *why* a specific release strategy was chosen, not just what happened,
  typically accessed via a licensed archive or API rather than scraping.

**How to execute that expansion**, concretely: each source above becomes a batch of real
documents (or structured records converted to short prose summaries) ingested via
`ingest_document(title, text, category="distribution-intelligence")` — the same function
`seed_distribution.py` already calls. No architecture changes needed; the collection
just grows. Licensing/access is the actual blocker for the box-office and panel-data
sources — the academic literature and trade press are the two categories realistically
ingestable without a paid data license, and would already meaningfully deepen the corpus
beyond the six seed documents.

## How the base engine works (single document or collection)

1. **Ingest** — paste text or upload a `.txt`/`.md` file. ContextCore splits it into
   ~600-character chunks on paragraph/sentence boundaries.
2. **Index** — builds a TF-IDF vector per chunk, in pure Python (no dependencies).
3. **Retrieve** — a question is vectorized the same way; cosine similarity ranks chunks;
   the top 4 are retrieved. For a collection, this pool spans every document tagged with
   that category, not just one document.
4. **Generate** — if `ANTHROPIC_API_KEY` is set and there's credit, Claude
   (`claude-opus-4-8`) composes an answer from the retrieved chunks and cites them by
   number. Otherwise, an **extractive** fallback returns the retrieved passages directly —
   the app always produces a real, grounded answer, never a fabricated one.

```
          ingest                          ask (document or collection)
  ┌────────────────────┐        ┌──────────────────────────────┐
  │ document(s)        │        │ question                     │
  │   │ chunk (~600ch)  │        │   │ TF-IDF query vector       │
  │   ▼                │        │   ▼                          │
  │ chunks ──► TF-IDF ─┼──────► │ cosine similarity ► top-k     │
  │        vector index│        │   │                           │
  └────────────────────┘        │   ▼                          │
                                │ retrieved chunks ─► answer    │
                                │   • Claude (if available)     │
                                │   • else extractive            │
                                │   + citations [Chunk n, title]│
                                └──────────────────────────────┘
```

## Knowledge graph (Phase 1 of PRODUCT-VISION.md)

Ingest also runs a second, independent step: Claude reads the document and extracts
its real entities (people, organizations, products, places, dates, concepts) and the
relationships between them, structured as JSON — one more Claude call, not a new ML
dependency. Those get stored and rendered as a graph (`/doc/<id>/graph` or
`/collection/<category>/graph`), built with NetworkX and laid out server-side as
inline SVG. A collection's graph pools entities across every document in it, merging
the same entity mentioned in multiple documents into a single node.

This needs `ANTHROPIC_API_KEY` with credit at ingest time, same as generation — with
no key, ingest still works exactly as before, it just skips this step and says so
honestly rather than showing an empty graph as if nothing was missing.

See `PRODUCT-VISION.md` for the full gap analysis and what's left (Phase 6,
scale-out — already researched separately in `SCALING-RESEARCH.md`).

## Confidence + conflict surfacing (Phase 2 of PRODUCT-VISION.md)

Every answer carries a **confidence** badge — high, medium, or low — derived
from the retrieval step's own cosine-similarity scores: the top score, and
the gap to the runner-up. A big gap means one passage clearly answers the
question; a small gap means several similarly-scored passages exist, which
is exactly the situation where a conflict is possible. No new model, no API
call — it's always present, even with zero API credit.

When a collection question's top passages come from more than one document,
a second, targeted Claude call asks specifically whether those passages
disagree with each other (not just cover different aspects of the topic).
If they do, the UI shows a conflict banner with a short explanation instead
of quietly picking one answer. This step does need `ANTHROPIC_API_KEY` with
credit — with none, it says so plainly (`conflict_note`) rather than
reporting "no conflict" when it never actually checked.

## Multi-format ingest (Phase 3 of PRODUCT-VISION.md)

Upload isn't limited to `.txt`/`.md` anymore. `parsers.py` turns each format
into plain text with one small, purpose-built library — PyMuPDF for PDF,
`python-docx` for DOCX, `openpyxl` for XLSX (sheet-by-sheet, row values
joined), `python-pptx` for PPTX (slide-by-slide, all text frames), and the
standard library's `csv`/`email` modules for `.csv`/`.eml`. Whatever comes
out gets handed to the exact same `chunk_text()` → `ingest_document()` path
every other document uses — nothing downstream (retrieval, generation,
entity extraction, confidence, conflict detection) had to change. A file
that's corrupt, password-protected, or an unrecognized extension returns a
clear error instead of silently ingesting nothing.

## OCR (Phase 4 of PRODUCT-VISION.md)

`.png`/`.jpg`/`.jpeg` uploads run through `pytesseract`, which wraps the
real Tesseract OCR engine — a system binary, not just a pip package. Install
it separately:

```bash
winget install UB-Mannheim.TesseractOCR      # Windows
pip install pytesseract
```

`parsers.py` checks the standard Windows install path automatically (and
falls back to `PATH`), so no extra configuration is needed once it's
installed. Without it, uploading an image returns a clear "Tesseract OCR is
not installed" error instead of a generic parse failure or a silently empty
document.

## Multi-hop reasoning (Phase 5 of PRODUCT-VISION.md)

The **Connect** page (`/connect`) answers "how are these two things related?"
by running a real NetworkX shortest-path search across the whole knowledge
graph — every ingested document's entities and relationships pooled
together, not just one document or one collection. Two entities can end up
connected through a chain that crosses documents that never mention each
other directly; that cross-document chain is the actual multi-hop case a
single retrieve-then-answer question can't do. The traversal itself is
deterministic graph math, so it works with zero API credit; when Claude is
available, a short plain-English explanation of the chain is layered on top.

Every document page also lists **related documents** — others that share at
least one real extracted entity, ranked by how many, so "what should I read
next" is a graph fact rather than a text-similarity guess.

## Hybrid retrieval at scale (Phase 6 of PRODUCT-VISION.md, §5 of SCALING-RESEARCH.md)

Every `ask` now runs through `hybrid_retrieval.py`'s `hybrid_retrieve()`, which fuses two
independent signals with Reciprocal Rank Fusion and reranks the result:

- **Sparse (BM25)** — real lexical scoring (`rank_bm25`), always on, no external
  dependency. This is what runs today.
- **Dense (embeddings + pgvector)** — semantic search that catches what BM25 can't
  ("movie" matching a chunk that only says "film"). Needs an embedding API key and the
  Postgres+pgvector service in `docker-compose.yml` running (`docker compose up -d`).
  Tries `OPENROUTER_API_KEY` first (OpenRouter's OpenAI-compatible `/embeddings`
  endpoint, `openai/text-embedding-3-small` — already part of this ecosystem's toolkit
  elsewhere), falling back to `VOYAGE_API_KEY` (`voyage-4-lite`) if OpenRouter isn't
  configured. Chunks are embedded once at ingest time, not per query — the actual fix
  for the "rebuild the whole index on every question" ceiling described in
  `SCALING-RESEARCH.md` §3.1.
- **Reranking** — `BAAI/bge-reranker-v2-m3`, self-hosted via `sentence-transformers`, no
  API key, runs over the fused candidates whenever the dense leg is active.

Without the Postgres service or the Voyage key, retrieval silently drops to BM25-only —
every `ask` response includes `retrieval_mode` (`"hybrid+rerank"` / `"sparse-only"` / etc.)
and `retrieval_note` so it's never silent about which rung it's actually running on.

## How to run locally

```bash
cd companies/contextcore
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt                     # Flask; anthropic is optional
python seed_distribution.py                         # one-time: seed the distribution-intelligence collection
python app.py
```

Open <http://127.0.0.1:5107>. Ingest a document from the homepage for single-document Q&A,
or open the **Collections** section to try the seeded `distribution-intelligence`
collection — either through its structured form or by typing a free-form question.

> Note: this repo's Anthropic account currently has a $0 credit balance, so the
> generative layer will report the API error and fall back to extractive answers.
> Add credit at console.anthropic.com to enable Claude-composed answers.

To enable Claude-composed answers:

```bash
pip install anthropic
set ANTHROPIC_API_KEY=sk-ant-...      # Windows (use `export` on macOS/Linux)
```

To enable dense retrieval (hybrid search's semantic leg):

```bash
docker compose up -d                  # starts Postgres + pgvector (docker-compose.yml)
set OPENROUTER_API_KEY=sk-or-...      # preferred — Windows (use `export` on macOS/Linux)
# or: set VOYAGE_API_KEY=pa-...       # fallback, from voyageai.com, if you'd rather use that
```

Restart `python app.py` afterward — it logs whether the pgvector schema connected
successfully at startup. Already-ingested documents won't retroactively get embeddings;
re-ingest them (or just add new ones) once both are set up.

## Stack

- Backend: Python Flask + SQLite; TF-IDF retrieval in pure Python (stdlib only)
- `parsers.py` — multi-format ingest: PyMuPDF, `python-docx`, `openpyxl`, `python-pptx`,
  plus stdlib `csv`/`email` (see "Multi-format ingest" above)
- `hybrid_retrieval.py` — BM25 + pgvector dense search + RRF fusion + cross-encoder
  reranking (see "Hybrid retrieval at scale" above); `docker-compose.yml` runs the
  Postgres+pgvector service it talks to
- Optional: `anthropic` SDK for the generative layer, entity extraction, and conflict detection
- Frontend: hand-written HTML/CSS/JS chat UI, no frameworks
- `distribution_intelligence.py` — form vocabulary + question-template builder only,
  no analysis logic (see "Case study" above)
- `seed_distribution.py` — one-time seed script for the `distribution-intelligence`
  collection's six real case-study documents
