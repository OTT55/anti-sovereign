# ContextCore — Product Vision & Gap Analysis

**Status: Phase 0 through 5 are built. Phase 6 (scale-out) is in progress —
see the status line in SCALING-RESEARCH.md for exactly what's live.**
This document exists to turn a big, ambitious spec into an honest map of what
exists today, what's genuinely missing, and what to build next — in order,
each phase shipping something real, not a stub.

## The vision, in one line

ContextCore should stop being "search over chunks" and become an org's
**domain intelligence layer**: documents in, a system that understands
entities, relationships, and contradictions between them, and answers that
show their evidence and their uncertainty — not just retrieval, reasoning.

The founder's own framing (verbatim intent, condensed):

> Traditional RAG: Document → Chunk → Embed → Retrieve → Answer.
> ContextCore: Documents → Extract Knowledge → Build Relationships →
> Knowledge Graph → Index → Reason → Verify → Answer.
> The AI should understand the organization before responding.

That's a real, different shape of product from what exists today. This
document does not water that down — it sequences it.

## What exists right now (honest inventory)

| Capability | State |
|---|---|
| Ingest `.txt`/`.md` text or pasted text | Real, working |
| Chunking (~600 char, paragraph/sentence boundaries) | Real, working |
| TF-IDF vector index, pure Python | Real, working |
| Cosine-similarity retrieval, top-k | Real, working |
| Claude-composed answer with citations | Real, working (needs API credit) |
| Extractive fallback (no API key/credit) | Real, working — always grounded, never fabricated |
| Collections (named, persistent, multi-document, pooled retrieval) | Real, working (`distribution-intelligence`) |
| Entity/relationship extraction | Real, working (needs API credit) — Phase 1 |
| Knowledge graph (`/doc/<id>/graph`, `/collection/<c>/graph`) | Real, working — NetworkX + inline SVG, Phase 1 |
| Multi-format parsing (PDF/DOCX/XLSX/PPTX/CSV/email) | Real, working — Phase 3 |
| OCR (PNG/JPG image ingest) | Real, working (needs the Tesseract binary installed) — Phase 4 |
| Confidence scoring on answers | Real, working — top-score + gap surfaced as high/medium/low, Phase 2 |
| Contradiction/conflict detection | Real, working (needs API credit) — targeted Claude call across multi-document hits, Phase 2 |
| Multi-hop reasoning (entity-to-entity graph traversal) | Real, working — Phase 5 |
| Graph-explorer UI | Static SVG only — no drag/zoom/interactivity yet |

This is not a criticism of the current build — TF-IDF retrieval + citation +
honest fallback is a real, correctly-scoped MVP. It's the floor the vision
gets built on, not a wrong direction to abandon.

## Grounded technology choices

Every choice below was checked against current (2026) practice, not assumed.

### Entity + relationship extraction: use Claude, not spaCy

Few-shot LLM extraction (Claude/GPT) now matches or exceeds supervised NER
models like spaCy on real-world entity/relationship extraction, without
needing thousands of hand-labeled training examples — and unlike spaCy,
handles *relationship* extraction natively, which spaCy has no real
pretrained models for. Since ContextCore already has the Anthropic SDK
wired in for answer generation, extraction is one more structured Claude
call per ingested document — no new ML dependency, no training pipeline.
**Recommendation: run entity+relationship extraction through Claude at
ingest time, not spaCy.**

### The graph itself: NetworkX, not Neo4j

NetworkX is a Python library imported into the existing Flask process —
nothing to deploy, nothing to keep running, a graph built and queried
directly in code. Neo4j is a separate database server, worth it once many
users/services need concurrent read/write access to the same graph or it
must survive restarts independent of the app process. At ContextCore's
current scale (one process, one SQLite file, low concurrent usage),
NetworkX is the correct fit — it can be persisted to the existing SQLite
file as adjacency data and rebuilt/cached in memory on load.
**Recommendation: NetworkX now; revisit Neo4j only if/when multi-user
concurrent graph writes become a real requirement (see SCALING-RESEARCH.md
for the equivalent scale-triggered decision on retrieval infrastructure).**

### Multi-format parsing: format-specific libraries, not a heavy framework

Unstructured.io-style all-in-one parsers (Unstructured, LlamaParse, Docling)
exist and are real 2026 options, but they're heavy dependencies for what's
needed here. Consistent with this codebase's existing philosophy (hand-rolled
TF-IDF instead of LangChain/LlamaIndex — see SCALING-RESEARCH.md), the
lighter, more auditable path is one small library per format:

| Format | Library |
|---|---|
| PDF | PyMuPDF (`fitz`) |
| DOCX | `python-docx` |
| XLSX | `openpyxl` |
| PPTX | `python-pptx` |
| CSV | stdlib `csv` |
| Email (`.eml`) | stdlib `email` |
| Images (OCR) | `pytesseract` — **requires the Tesseract binary installed on the machine, not just a pip package; this is the one real external dependency in this table and should be called out plainly in the README when it lands, not glossed over** |

Each parser's job is identical: produce plain text, then hand it to the
*existing* `chunk_text()` → `ingest_document()` pipeline unchanged. No
retrieval-layer changes needed for this phase.

### Confidence + conflict detection: reuse retrieval, don't bolt on a new system

Confidence doesn't need a new model. The retrieval step already produces a
cosine-similarity score per chunk (visible today in every citation's
`score` field, just not surfaced as "confidence" in the UI). A real,
honest confidence signal: the top score itself, and the *gap* between the
top score and the next one — a big gap means one passage clearly answers
the question; a small gap or multiple similar-scoring chunks from different
documents saying different things is exactly the "I found conflicting
information" case the vision asks for. Detecting an actual *contradiction*
(not just topical overlap) is a genuine reasoning task — the honest way to
build it is a targeted Claude call over the top-k retrieved chunks asking
specifically "do any of these passages disagree with each other, and if so
how" — not a bespoke NLP contradiction classifier, which would be a
multi-month research project on its own.

## Phased roadmap

Each phase below ships a real, working increment — nothing partial, nothing
mocked, consistent with this project's no-placeholders rule.

**Phase 0 — done.** Single-document + collection RAG, TF-IDF retrieval,
citations, Claude/extractive answers.

**Phase 1 — Entity + relationship extraction, and a real graph.**
On ingest, send the document (or each chunk) to Claude with a structured
extraction prompt; store entities and relationships in new SQLite tables;
build a NetworkX graph from them at query time; add a `/doc/<id>/graph`
(and `/collection/<category>/graph`) view rendering it. This is the single
highest-leverage step — it's the actual "knowledge graph" the vision names,
and it's buildable on top of what exists without touching the retrieval core.

**Phase 2 — done.** Confidence + conflict surfacing.
Every answer now carries a `confidence` field (`high`/`medium`/`low`, from
the top retrieval score and the gap to the runner-up — no new model). When
the top-k hits in a collection query span more than one document, a
targeted Claude call checks whether the passages actually disagree (not
just cover different ground) and the UI shows a conflict banner instead of
silently picking one answer. Like extraction, this needs API credit to run
its Claude step (the conflict check); with no key it says so honestly
(`conflict_note`) rather than claiming "no conflict" when it never checked.
Confidence itself needs no API call — it's a deterministic read of the
existing retrieval scores, so it's always present.

**Phase 3 — done.** Multi-format ingest.
PDF, DOCX, XLSX, PPTX, CSV, and `.eml` files are all parsed to plain text by
`parsers.py`, one small format-specific library per format (see the table
above) — then handed to the exact same `chunk_text()` → `ingest_document()`
pipeline `.txt`/`.md` already used. No retrieval-layer changes were needed,
as planned. A file that fails to parse (corrupt, password-protected, or an
unsupported extension) returns a clear error instead of a silent empty
document.

**Phase 4 — done.** OCR.
`.png`/`.jpg`/`.jpeg` files run through `pytesseract`, which shells out to
the real Tesseract OCR binary (installed via `winget install
UB-Mannheim.TesseractOCR` on this machine — a genuine system-level install,
not just `pip install pytesseract`). If the binary isn't found — checked at
the standard Windows install paths, falling back to `PATH` — ingest fails
with a clear, specific instruction to install it, rather than a generic
parse error or a silently empty document.

**Phase 5 — done.** Multi-hop / comparative reasoning.
Two real capabilities, both genuinely dependent on Phase 1's graph existing
first, as planned:

- **`/connect`** — given two entity names, `find_connection()` runs a real
  NetworkX shortest-path search across the *entire* graph (every ingested
  document pooled, not just one collection). Two entities can be connected
  through a chain that crosses documents that never reference each other
  directly — that's the actual multi-hop case a single retrieve-then-answer
  pass can't do. The traversal is deterministic and needs no API call; an
  optional short Claude narration is layered on top of the found chain,
  same honest-fallback pattern as everything else.
- **Related documents** (on every doc page) — `related_documents()` finds
  other documents sharing real extracted entities with the one you're
  looking at, ranked by how many, as a graph-grounded "what to read next"
  instead of a generic text-similarity guess.

"What changed between Version 3 and Version 7" (true document-versioning
diff) was scoped out — ContextCore has no notion of one document being a
"version" of another, and inventing that data model wasn't worth it for
this phase. The entity-connection and related-document features above are
the real, buildable slice of "multi-hop reasoning" that exists today's data
model actually supports.

**Phase 6 — Scale-out.** Already researched separately — see
`SCALING-RESEARCH.md` for the retrieval-infrastructure math, vector DB
choice, and hybrid search plan once corpus size demands it.

## What this document deliberately does not do

It does not attempt Finance/Legal/Film/Engineering "workspace" specialization
as a Phase — that's a prompt/UI configuration layered on top of Phases 1–5
(domain-specific entity types, domain-specific extraction prompts), not a
separate architecture. It becomes buildable, cheaply, once Phase 1 exists;
building it before Phase 1 would mean hand-writing per-domain logic with
nothing underneath it to plug into — the same mistake the original
LaunchWindow rules-engine made before the merge.
