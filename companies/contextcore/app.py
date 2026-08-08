"""
ContextCore — retrieval-augmented generation over your own documents.

Seeds the Sovereign Stack company **ContextCore** (data refineries / enterprise
RAG). Upload a document; ContextCore splits it into chunks, builds a TF-IDF
vector index, and answers questions by retrieving the most relevant chunks and
citing exactly where each answer came from.

Retrieval is fully local and dependency-free (classical TF-IDF cosine similarity
in pure Python — the production system swaps in sentence-transformer embeddings
+ FAISS, but the architecture is identical). An optional generative layer sends
the retrieved chunks to Claude to compose a natural-language answer; when no API
key or credit is available, ContextCore falls back to an **extractive** answer
built from the retrieved passages, so the app always works end to end.

Run:  python app.py   →  http://127.0.0.1:5107
"""

import json
import math
import os
import re
import sqlite3
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, g, jsonify, render_template, request

from parsers import parse_file, UnsupportedFormat, SUPPORTED_EXTENSIONS
from hybrid_retrieval import hybrid_retrieve, store_chunk_embeddings, init_pgvector_schema

DB_PATH = Path(__file__).parent / "contextcore.db"
CLAUDE_MODEL = "claude-opus-4-8"
TOP_K = 4

app = Flask(__name__)

STOPWORDS = set(
    "the a an and or of to in on for with is are was were be been being this that "
    "these those it its as at by from into out over under then than so such but if "
    "how what when where who whom which why do does did done has have had not no".split()
)


# --------------------------------------------------------------------------
# Text processing: chunking + TF-IDF retrieval (pure Python)
# --------------------------------------------------------------------------

def tokenize(text):
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1 and t not in STOPWORDS]


def chunk_text(text, target=600):
    """Split into ~`target`-character chunks on paragraph/sentence boundaries."""
    paras = re.split(r"\n\s*\n", text.strip())
    chunks, buf = [], ""
    for p in paras:
        p = p.strip()
        if not p:
            continue
        if len(buf) + len(p) + 2 <= target:
            buf = (buf + "\n\n" + p).strip()
        else:
            if buf:
                chunks.append(buf)
            # a single long paragraph: split on sentences
            if len(p) > target:
                sentences = re.split(r"(?<=[.!?])\s+", p)
                buf = ""
                for s in sentences:
                    if len(buf) + len(s) + 1 <= target:
                        buf = (buf + " " + s).strip()
                    else:
                        if buf:
                            chunks.append(buf)
                        buf = s
            else:
                buf = p
    if buf:
        chunks.append(buf)
    return chunks


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


def retrieve(question, vectors, idf, k=TOP_K):
    q = query_vector(question, idf)
    scored = [(cosine(q, vec), i) for i, vec in enumerate(vectors)]
    scored.sort(reverse=True)
    return [(i, score) for score, i in scored[:k] if score > 0]


# --------------------------------------------------------------------------
# Optional generative layer (Claude). Fails gracefully.
# --------------------------------------------------------------------------

def generate_answer(question, passages):
    """Return (answer_text, mode, note). mode is 'generative' or 'extractive'."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return extractive_answer(passages), "extractive", \
            "No ANTHROPIC_API_KEY set — showing an extractive answer from the retrieved passages."
    try:
        import anthropic
    except ImportError:
        return extractive_answer(passages), "extractive", \
            "The `anthropic` package is not installed — showing an extractive answer. `pip install anthropic` to enable generation."
    context = "\n\n".join(f"[Chunk {i+1}] {text}" for i, text in passages)
    prompt = (
        "Answer the question using ONLY the context below. Cite the chunk numbers "
        "you used in square brackets, e.g. [Chunk 2]. If the context does not "
        f"contain the answer, say so.\n\nContext:\n{context}\n\nQuestion: {question}"
    )
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=CLAUDE_MODEL, max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text, "generative", None
    except Exception as e:  # billing, network, auth — surface honestly, keep working
        return extractive_answer(passages), "extractive", \
            f"Claude call failed ({type(e).__name__}: {e}). Showing an extractive answer instead."


def extractive_answer(passages):
    if not passages:
        return "No relevant passage was found in this document."
    return "Based on the most relevant passages:\n\n" + "\n\n".join(
        f"[Chunk {i+1}] {text}" for i, text in passages
    )


# --------------------------------------------------------------------------
# Confidence + conflict surfacing. Phase 2 of PRODUCT-VISION.md. Confidence
# reuses the retrieval score that already exists in every citation — no new
# model. Conflict detection is a targeted Claude call over the top-k passages,
# only run when they come from more than one document, same honesty pattern
# as generate_answer(): if it can't run, say so rather than silently
# reporting "no conflict."
# --------------------------------------------------------------------------

def assess_confidence(hits):
    """hits: (index, score) pairs already sorted desc by score from retrieve()
    or hybrid_retrieve(). top_score alone can mislead — a single strong match
    and three equally strong-but-different matches can share a top_score, so
    the gap to the runner-up is what actually distinguishes "one passage
    clearly answers this" from "the corpus has multiple, possibly
    conflicting, takes."

    Threshold caveat: these were calibrated against TF-IDF cosine similarity,
    which is what retrieval_mode "tfidf-fallback" and (via the sigmoid in
    hybrid_retrieval.rerank_candidates()) "hybrid+rerank" both produce —
    genuine [0,1] relevance scores. "sparse-only" (raw BM25) and "hybrid"
    (RRF-fused, unreranked) modes are on a different, unbounded scale, so
    the same thresholds read as directionally correct (higher top_score and
    bigger gap still means more confident) but aren't precisely calibrated
    for those two fallback rungs. Worth fixing with per-mode thresholds if
    "sparse-only"/"hybrid" confidence badges turn out to matter in practice —
    not done here to avoid tuning thresholds against scores this session has
    no real corpus to validate them on."""
    if not hits:
        return {"level": "none", "top_score": 0.0, "gap": 0.0}
    top_score = hits[0][1]
    gap = top_score - hits[1][1] if len(hits) > 1 else top_score
    if top_score >= 0.35 and gap >= 0.08:
        level = "high"
    elif top_score >= 0.15:
        level = "medium"
    else:
        level = "low"
    return {"level": level, "top_score": round(top_score, 3), "gap": round(gap, 3)}


CONFLICT_PROMPT = """Below are passages retrieved from different documents in response to
the same question. Determine whether any of them meaningfully disagree with each other —
not just cover different aspects of the topic, but actually contradict one another.
Respond with ONLY valid JSON (no markdown fences, no commentary), in exactly this shape:

{{"conflict": true|false, "explanation": "short human-readable explanation, empty string if no conflict"}}

Question: {question}

Passages:
{passages}"""


def detect_conflict(question, passages_with_source):
    """passages_with_source: [(text, source_label), ...]. Returns (result, note).
    result is None when the check didn't run (fewer than 2 distinct sources, no
    API key/credit, or a call failure) — None means "unknown," never "no conflict."
    """
    sources = {src for _, src in passages_with_source}
    if len(sources) < 2:
        return None, None
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None, "Conflict check skipped — no ANTHROPIC_API_KEY set."
    try:
        import anthropic
    except ImportError:
        return None, "Conflict check skipped — the `anthropic` package is not installed."

    passages_text = "\n\n".join(f"[{src}] {text}" for text, src in passages_with_source)
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=CLAUDE_MODEL, max_tokens=300,
            messages=[{"role": "user", "content": CONFLICT_PROMPT.format(question=question, passages=passages_text)}],
        )
        raw = msg.content[0].text.strip()
        raw = re.sub(r"^```(json)?|```$", "", raw, flags=re.MULTILINE).strip()
        data = json.loads(raw)
        return {"conflict": bool(data.get("conflict")), "explanation": (data.get("explanation") or "").strip()}, None
    except Exception as e:  # billing, network, auth, malformed JSON — surface honestly
        return None, f"Conflict check failed ({type(e).__name__}: {e})."


# --------------------------------------------------------------------------
# Entity + relationship extraction (Claude). Phase 1 of PRODUCT-VISION.md.
# Few-shot LLM extraction handles both entities AND relationships in one
# pass, which spaCy-style NER has no real pretrained models for — see
# PRODUCT-VISION.md for why this is Claude rather than a local NER model.
# Fails gracefully, same honesty pattern as generate_answer(): no key or no
# credit means no graph for this document, not a fabricated one.
# --------------------------------------------------------------------------

EXTRACTION_PROMPT = """Extract the real entities and relationships between them from the
text below. Respond with ONLY valid JSON (no markdown fences, no commentary), in exactly
this shape:

{{"entities": [{{"name": "...", "type": "person|organization|product|place|date|concept"}}],
  "relationships": [{{"source": "...", "target": "...", "label": "short verb phrase"}}]}}

Rules:
- Only extract entities that are actually named or clearly identified in the text.
- Every "source" and "target" in relationships must exactly match a "name" in entities.
- If the text has no clear entities, return {{"entities": [], "relationships": []}}.

Text:
{text}"""


def extract_entities_relationships(db, doc_id, text):
    """Best-effort entity/relationship extraction for one document.

    Returns (entity_count, relationship_count, note). note is None on success,
    or an honest explanation of why extraction didn't run/failed — mirrors
    generate_answer()'s extractive-fallback pattern rather than silently
    producing an empty graph and calling it done.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return 0, 0, "No ANTHROPIC_API_KEY set — entity extraction skipped for this document."
    try:
        import anthropic
    except ImportError:
        return 0, 0, "The `anthropic` package is not installed — entity extraction skipped."

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=CLAUDE_MODEL, max_tokens=1500,
            messages=[{"role": "user", "content": EXTRACTION_PROMPT.format(text=text[:6000])}],
        )
        raw = msg.content[0].text.strip()
        raw = re.sub(r"^```(json)?|```$", "", raw, flags=re.MULTILINE).strip()
        data = json.loads(raw)
    except Exception as e:  # billing, network, auth, malformed JSON — surface honestly
        return 0, 0, f"Entity extraction failed ({type(e).__name__}: {e})."

    name_to_id = {}
    for e in data.get("entities", []):
        name = (e.get("name") or "").strip()
        etype = (e.get("type") or "concept").strip()
        if not name or name in name_to_id:
            continue
        cur = db.execute(
            "INSERT INTO entities (doc_id, name, type) VALUES (?, ?, ?)",
            (doc_id, name, etype),
        )
        name_to_id[name] = cur.lastrowid

    rel_count = 0
    for r in data.get("relationships", []):
        src_id = name_to_id.get((r.get("source") or "").strip())
        tgt_id = name_to_id.get((r.get("target") or "").strip())
        label = (r.get("label") or "related to").strip()
        if src_id is None or tgt_id is None or src_id == tgt_id:
            continue
        db.execute(
            "INSERT INTO relationships (doc_id, source_id, target_id, label) VALUES (?, ?, ?, ?)",
            (doc_id, src_id, tgt_id, label),
        )
        rel_count += 1

    db.commit()
    return len(name_to_id), rel_count, None


def load_graph(db, doc_ids):
    """Load entities + relationships across one or more documents, deduping
    entities by (name, type) so the same person/org mentioned in multiple
    documents in a collection becomes one node, not several."""
    placeholders = ",".join("?" for _ in doc_ids)
    ent_rows = db.execute(
        f"SELECT id, doc_id, name, type FROM entities WHERE doc_id IN ({placeholders})",
        doc_ids,
    ).fetchall()
    rel_rows = db.execute(
        f"""SELECT r.source_id, r.target_id, r.label, r.doc_id
            FROM relationships r WHERE r.doc_id IN ({placeholders})""",
        doc_ids,
    ).fetchall()

    key_of_row_id = {}
    nodes = {}  # (name, type) -> {name, type, doc_ids: set}
    for r in ent_rows:
        key = (r["name"], r["type"])
        key_of_row_id[r["id"]] = key
        if key not in nodes:
            nodes[key] = {"name": r["name"], "type": r["type"], "doc_ids": set()}
        nodes[key]["doc_ids"].add(r["doc_id"])

    edges = []
    for r in rel_rows:
        src, tgt = key_of_row_id.get(r["source_id"]), key_of_row_id.get(r["target_id"])
        if src is None or tgt is None:
            continue
        edges.append({"source": src, "target": tgt, "label": r["label"]})

    return nodes, edges


def graph_svg(nodes, edges, width=760, height=520):
    """Render a knowledge graph as inline SVG using a NetworkX spring layout.
    Static (no drag/zoom) — full interactivity is a later phase per
    PRODUCT-VISION.md; this phase's job is a real graph, not a polished one."""
    import networkx as nx
    from xml.sax.saxutils import escape

    if not nodes:
        return None

    g = nx.Graph()
    for key in nodes:
        g.add_node(key)
    for e in edges:
        g.add_edge(e["source"], e["target"])

    pos = nx.spring_layout(g, seed=42, k=1.6 / max(len(nodes), 1) ** 0.5)
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    pad = 60

    def scale(x, y):
        sx = pad + (x - x_min) / (x_max - x_min or 1) * (width - 2 * pad)
        sy = pad + (y - y_min) / (y_max - y_min or 1) * (height - 2 * pad)
        return sx, sy

    coords = {key: scale(*pos[key]) for key in nodes}

    parts = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" font-family="system-ui,sans-serif">']
    for e in edges:
        if e["source"] not in coords or e["target"] not in coords:
            continue
        x1, y1 = coords[e["source"]]
        x2, y2 = coords[e["target"]]
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#2a222c" stroke-width="1.5"/>')
        parts.append(f'<text x="{mx:.1f}" y="{my:.1f}" fill="#8f8593" font-size="9.5" text-anchor="middle">{escape(e["label"])}</text>')
    for key, (x, y) in coords.items():
        name, etype = key
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="#d44e8f"/>')
        parts.append(f'<text x="{x:.1f}" y="{y - 12:.1f}" fill="#ececf0" font-size="11.5" text-anchor="middle" font-weight="600">{escape(name)}</text>')
        parts.append(f'<text x="{x:.1f}" y="{y + 20:.1f}" fill="#8f8593" font-size="9.5" text-anchor="middle" text-transform="uppercase">{escape(etype)}</text>')
    parts.append("</svg>")
    return "".join(parts)


# --------------------------------------------------------------------------
# Multi-hop / comparative reasoning. Phase 5 of PRODUCT-VISION.md. The graph
# traversal itself is deterministic (NetworkX shortest-path over the real
# entities/relationships from Phase 1) — no API call needed, so this works
# even with zero credit. A short Claude-written explanation is layered on
# top, same honest-fallback pattern as everything else: with no key, you
# still get the real chain, just without the plain-English narration.
# --------------------------------------------------------------------------

def find_connection(nodes, edges, from_name, to_name):
    """Shortest path between two entities across the *whole* graph (every
    ingested document, not just one collection) — genuine multi-hop
    reasoning: the chain can cross documents that never cite each other
    directly, linked only through a shared entity in between.

    Returns (hops, error). hops is a list of {name, type, doc_ids, via}
    dicts (via is absent on the first hop), or None if either name can't be
    resolved or no path connects them — error explains which.
    """
    import networkx as nx

    def resolve(name):
        needle = name.strip().lower()
        for key in nodes:
            if key[0].lower() == needle:
                return key
        return None

    src_key, tgt_key = resolve(from_name), resolve(to_name)
    if src_key is None:
        return None, f"'{from_name}' wasn't found as an entity in any ingested document."
    if tgt_key is None:
        return None, f"'{to_name}' wasn't found as an entity in any ingested document."

    g = nx.Graph()
    g.add_nodes_from(nodes)
    edge_label = {}
    for e in edges:
        g.add_edge(e["source"], e["target"])
        edge_label[frozenset((e["source"], e["target"]))] = e["label"]

    try:
        path = nx.shortest_path(g, src_key, tgt_key)
    except nx.NetworkXNoPath:
        return None, f"'{from_name}' and '{to_name}' are both in the graph, but no chain of relationships connects them yet."

    hops = []
    for i, key in enumerate(path):
        hop = {"name": key[0], "type": key[1], "doc_ids": sorted(nodes[key]["doc_ids"])}
        if i > 0:
            hop["via"] = edge_label.get(frozenset((path[i - 1], key)), "related to")
        hops.append(hop)
    return hops, None


CONNECTION_EXPLAIN_PROMPT = """A knowledge-graph search found this chain of real
relationships connecting two entities, hop by hop. Write a short (2-4 sentence),
plain-English explanation of the connection, using ONLY the facts in the chain
below — do not invent anything not stated here.

Chain: {chain}"""


def explain_connection(hops):
    """Best-effort plain-English narration of a found path. (None, None) if
    trivial (path of length 1, i.e. searching an entity against itself).
    Mirrors generate_answer()'s fallback pattern — no key/credit means no
    narration, not a fabricated one."""
    if len(hops) < 2:
        return None, None
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None, "No ANTHROPIC_API_KEY set — showing the raw connection path only."
    try:
        import anthropic
    except ImportError:
        return None, "The `anthropic` package is not installed — showing the raw connection path only."

    chain = hops[0]["name"]
    for h in hops[1:]:
        chain += f" --[{h['via']}]--> {h['name']}"
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=CLAUDE_MODEL, max_tokens=200,
            messages=[{"role": "user", "content": CONNECTION_EXPLAIN_PROMPT.format(chain=chain)}],
        )
        return msg.content[0].text.strip(), None
    except Exception as e:
        return None, f"Explanation failed ({type(e).__name__}: {e}). Showing the raw connection path only."


def related_documents(db, doc_id, limit=6):
    """Other documents sharing at least one real extracted entity with this
    one, ranked by how many they share — a deterministic, graph-grounded
    "read next" signal, not a generic similarity score."""
    rows = db.execute(
        """SELECT e2.doc_id, d.title, COUNT(DISTINCT e2.name || '|' || e2.type) shared,
                  GROUP_CONCAT(DISTINCT e2.name) names
           FROM entities e1
           JOIN entities e2 ON e1.name = e2.name AND e1.type = e2.type AND e2.doc_id != e1.doc_id
           JOIN documents d ON d.doc_id = e2.doc_id
           WHERE e1.doc_id = ?
           GROUP BY e2.doc_id, d.title
           ORDER BY shared DESC
           LIMIT ?""",
        (doc_id, limit),
    ).fetchall()
    return [
        {"doc_id": r["doc_id"], "title": r["title"], "shared": r["shared"], "names": r["names"].split(",")}
        for r in rows
    ]


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS documents (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id     TEXT NOT NULL UNIQUE,
            title      TEXT NOT NULL,
            category   TEXT NOT NULL DEFAULT 'general',
            created_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS chunks (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id   TEXT NOT NULL,
            seq      INTEGER NOT NULL,
            text     TEXT NOT NULL
        )"""
    )
    # Migration for pre-existing databases created before `category` existed.
    cols = [r[1] for r in conn.execute("PRAGMA table_info(documents)").fetchall()]
    if "category" not in cols:
        conn.execute("ALTER TABLE documents ADD COLUMN category TEXT NOT NULL DEFAULT 'general'")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS entities (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id TEXT NOT NULL,
            name   TEXT NOT NULL,
            type   TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS relationships (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id    TEXT NOT NULL,
            source_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            label     TEXT NOT NULL
        )"""
    )
    conn.commit()
    conn.close()


def load_chunks(db, doc_id):
    rows = db.execute(
        "SELECT id, text FROM chunks WHERE doc_id = ? ORDER BY seq ASC", (doc_id,)
    ).fetchall()
    return [{"id": r["id"], "text": r["text"]} for r in rows]


def load_collection_chunks(db, category):
    """Pool chunks across every document in a category, tagged with their source doc."""
    rows = db.execute(
        """SELECT c.id, c.text, c.seq, d.doc_id, d.title
           FROM chunks c JOIN documents d ON d.doc_id = c.doc_id
           WHERE d.category = ?
           ORDER BY d.id ASC, c.seq ASC""",
        (category,),
    ).fetchall()
    return [{"id": r["id"], "text": r["text"], "doc_id": r["doc_id"], "title": r["title"]} for r in rows]


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@app.route("/")
def index():
    db = get_db()
    docs = db.execute(
        """SELECT d.doc_id, d.title, d.created_at, COUNT(c.id) chunks
           FROM documents d LEFT JOIN chunks c ON c.doc_id = d.doc_id
           WHERE d.category = 'general'
           GROUP BY d.doc_id ORDER BY d.id DESC"""
    ).fetchall()
    collections = db.execute(
        """SELECT d.category, COUNT(DISTINCT d.doc_id) doc_count, COUNT(c.id) chunk_count
           FROM documents d LEFT JOIN chunks c ON c.doc_id = d.doc_id
           WHERE d.category != 'general'
           GROUP BY d.category ORDER BY d.category ASC"""
    ).fetchall()
    return render_template("index.html", docs=docs, collections=collections, supported_extensions=SUPPORTED_EXTENSIONS)


def ingest_document(title, text, category="general"):
    """Shared ingest path used by the /ingest route and by seed scripts.

    Returns (doc_id, chunk_count, entity_count, relationship_count, extraction_note, embedding_note).
    """
    chunks = chunk_text(text)
    if not chunks:
        return None, 0, 0, 0, None, None
    doc_id = "CX-" + uuid.uuid4().hex[:10].upper()
    db = get_db()
    db.execute(
        "INSERT INTO documents (doc_id, title, category, created_at) VALUES (?, ?, ?, ?)",
        (doc_id, title, category, datetime.now(timezone.utc).isoformat()),
    )
    db.executemany(
        "INSERT INTO chunks (doc_id, seq, text) VALUES (?, ?, ?)",
        [(doc_id, i, c) for i, c in enumerate(chunks)],
    )
    db.commit()
    entity_count, rel_count, note = extract_entities_relationships(db, doc_id, text)

    # Dense embeddings — Phase 6 of SCALING-RESEARCH.md. Embed once here, at
    # ingest time, so query time never re-embeds anything (that per-query
    # rebuild is exactly the compute ceiling §3.1 describes). Best-effort:
    # no Voyage key or no reachable Postgres just means this document stays
    # on the sparse (BM25) retrieval rung, same honest-degradation pattern
    # as everything else — ingest itself never fails because of this.
    chunk_rows = db.execute(
        "SELECT id, text FROM chunks WHERE doc_id = ? ORDER BY seq ASC", (doc_id,)
    ).fetchall()
    _, embedding_note = store_chunk_embeddings(doc_id, [(r["id"], r["text"]) for r in chunk_rows])

    return doc_id, len(chunks), entity_count, rel_count, note, embedding_note


@app.route("/ingest", methods=["POST"])
def ingest():
    title = (request.form.get("title") or "").strip()
    text = request.form.get("text") or ""
    category = (request.form.get("category") or "general").strip() or "general"
    file = request.files.get("file")
    if file and file.filename:
        raw = file.read()
        try:
            text = parse_file(file.filename, raw)
        except UnsupportedFormat as e:
            return jsonify(error=str(e)), 400
        if not title:
            title = file.filename
    text = text.strip()
    if not title or not text:
        return jsonify(error="A title and some document text are required."), 400

    doc_id, chunk_count, entity_count, rel_count, extraction_note, embedding_note = ingest_document(title, text, category)
    if doc_id is None:
        return jsonify(error="Could not extract any text to index."), 400
    return jsonify(
        doc_id=doc_id, chunk_count=chunk_count,
        entity_count=entity_count, relationship_count=rel_count, extraction_note=extraction_note,
        embedding_note=embedding_note,
    )


@app.get("/api/search")
def api_search():
    """Read-only search across documents and collections, for the command
    palette. Additive endpoint — doesn't touch any existing route."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 1:
        return jsonify(results=[])
    like = f"%{q}%"
    db = get_db()
    results = []
    for d in db.execute(
        "SELECT doc_id, title, category FROM documents WHERE title LIKE ? ORDER BY id DESC LIMIT 8",
        (like,),
    ).fetchall():
        results.append({"type": "Document", "title": d["title"], "subtitle": d["doc_id"],
                         "url": f"/doc/{d['doc_id']}"})
    for c in db.execute(
        "SELECT DISTINCT category FROM documents WHERE category != 'general' AND category LIKE ? LIMIT 6",
        (like,),
    ).fetchall():
        results.append({"type": "Collection", "title": c["category"], "subtitle": "",
                         "url": f"/collection/{c['category']}"})
    return jsonify(results=results)


@app.get("/api/documents/latest")
def api_documents_latest():
    """Read-only: most recently indexed general documents, for client-side
    polling so newly-ingested work appears without a refresh. Additive."""
    limit = min(int(request.args.get("limit") or 5), 20)
    db = get_db()
    rows = db.execute(
        """SELECT d.doc_id, d.title, d.created_at, COUNT(c.id) chunks
           FROM documents d LEFT JOIN chunks c ON c.doc_id = d.doc_id
           WHERE d.category = 'general'
           GROUP BY d.doc_id ORDER BY d.id DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    total = db.execute("SELECT COUNT(*) c FROM documents WHERE category='general'").fetchone()["c"]
    return jsonify(docs=[dict(r) for r in rows], total=total)


@app.route("/doc/<doc_id>")
def doc_page(doc_id):
    db = get_db()
    doc = db.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
    if not doc:
        abort(404)
    chunks = load_chunks(db, doc_id)
    entity_count = db.execute("SELECT COUNT(*) c FROM entities WHERE doc_id = ?", (doc_id,)).fetchone()["c"]
    related = related_documents(db, doc_id) if entity_count else []
    return render_template("doc.html", doc=doc, chunk_count=len(chunks), entity_count=entity_count, related=related)


@app.route("/doc/<doc_id>/graph")
def doc_graph(doc_id):
    db = get_db()
    doc = db.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
    if not doc:
        abort(404)
    nodes, edges = load_graph(db, [doc_id])
    svg = graph_svg(nodes, edges)
    return render_template(
        "graph.html", title=doc["title"], back_href=f"/doc/{doc_id}", back_label=doc["title"],
        nodes=nodes.values(), edges=edges, svg=svg,
    )


@app.route("/connect")
def connect():
    from_name = (request.args.get("from") or "").strip()
    to_name = (request.args.get("to") or "").strip()
    searched = bool(from_name and to_name)

    hops, error, explanation, explanation_note = None, None, None, None
    if searched:
        db = get_db()
        all_doc_ids = [r["doc_id"] for r in db.execute("SELECT doc_id FROM documents").fetchall()]
        nodes, edges = load_graph(db, all_doc_ids) if all_doc_ids else ({}, [])
        hops, error = find_connection(nodes, edges, from_name, to_name)
        if hops:
            explanation, explanation_note = explain_connection(hops)

    return render_template(
        "connect.html", from_name=from_name, to_name=to_name, searched=searched,
        hops=hops, error=error, explanation=explanation, explanation_note=explanation_note,
    )


@app.route("/doc/<doc_id>/ask", methods=["POST"])
def ask(doc_id):
    db = get_db()
    if not db.execute("SELECT 1 FROM documents WHERE doc_id = ?", (doc_id,)).fetchone():
        return jsonify(error="Unknown document."), 404
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify(error="Ask a question."), 400

    chunk_rows = load_chunks(db, doc_id)
    chunk_ids = [c["id"] for c in chunk_rows]
    chunks = [c["text"] for c in chunk_rows]
    hits, retrieval_mode, retrieval_note = hybrid_retrieve(question, chunk_ids, chunks)
    passages = [(i, chunks[i]) for i, _ in hits]
    answer, mode, note = generate_answer(question, passages)
    confidence = assess_confidence(hits)

    citations = [{
        "chunk": i + 1,
        "score": round(score, 3),
        "preview": chunks[i][:220] + ("…" if len(chunks[i]) > 220 else ""),
    } for i, score in hits]

    return jsonify(
        answer=answer, mode=mode, note=note, citations=citations, confidence=confidence,
        retrieval_mode=retrieval_mode, retrieval_note=retrieval_note,
    )


# --------------------------------------------------------------------------
# Collections: a category is a growable, persistent corpus of many documents,
# queried as one pool. This is the same chunk/TF-IDF/generate engine above —
# a collection is just retrieval spanning multiple documents instead of one.
# --------------------------------------------------------------------------

@app.route("/collection/<category>")
def collection_page(category):
    db = get_db()
    docs = db.execute(
        """SELECT d.doc_id, d.title, COUNT(c.id) chunks
           FROM documents d LEFT JOIN chunks c ON c.doc_id = d.doc_id
           WHERE d.category = ? GROUP BY d.doc_id ORDER BY d.id ASC""",
        (category,),
    ).fetchall()
    if not docs:
        abort(404)

    from distribution_intelligence import GENRES, TIERS, COLLECTION_CATEGORY

    is_distribution = category == COLLECTION_CATEGORY
    entity_count = db.execute(
        "SELECT COUNT(*) c FROM entities WHERE doc_id IN "
        f"({','.join('?' for _ in docs)})", [d["doc_id"] for d in docs],
    ).fetchone()["c"]
    return render_template(
        "collection.html",
        category=category,
        docs=docs,
        is_distribution=is_distribution,
        genres=GENRES if is_distribution else None,
        tiers=TIERS if is_distribution else None,
        entity_count=entity_count,
    )


@app.route("/collection/<category>/graph")
def collection_graph(category):
    db = get_db()
    doc_ids = [r["doc_id"] for r in db.execute(
        "SELECT doc_id FROM documents WHERE category = ?", (category,)
    ).fetchall()]
    if not doc_ids:
        abort(404)
    nodes, edges = load_graph(db, doc_ids)
    svg = graph_svg(nodes, edges)
    return render_template(
        "graph.html", title=category, back_href=f"/collection/{category}", back_label=f"Collection: {category}",
        nodes=nodes.values(), edges=edges, svg=svg,
    )


@app.route("/collection/<category>/ask", methods=["POST"])
def collection_ask(category):
    db = get_db()
    collection_chunks = load_collection_chunks(db, category)
    if not collection_chunks:
        return jsonify(error="Unknown or empty collection."), 404

    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify(error="Ask a question."), 400

    chunk_ids = [c["id"] for c in collection_chunks]
    texts = [c["text"] for c in collection_chunks]
    hits, retrieval_mode, retrieval_note = hybrid_retrieve(question, chunk_ids, texts)
    passages = [(i, texts[i]) for i, _ in hits]
    answer, mode, note = generate_answer(question, passages)
    confidence = assess_confidence(hits)
    conflict, conflict_note = detect_conflict(
        question, [(texts[i], collection_chunks[i]["title"]) for i, _ in hits]
    )

    citations = [{
        "chunk": i + 1,
        "score": round(score, 3),
        "doc_title": collection_chunks[i]["title"],
        "doc_id": collection_chunks[i]["doc_id"],
        "preview": texts[i][:220] + ("…" if len(texts[i]) > 220 else ""),
    } for i, score in hits]

    return jsonify(
        answer=answer, mode=mode, note=note, citations=citations, question=question,
        confidence=confidence, conflict=conflict, conflict_note=conflict_note,
        retrieval_mode=retrieval_mode, retrieval_note=retrieval_note,
    )


if __name__ == "__main__":
    init_db()
    try:
        init_pgvector_schema()
        print("pgvector schema ready — dense retrieval available (subject to OPENROUTER_API_KEY or VOYAGE_API_KEY).")
    except Exception as e:
        print(f"pgvector unavailable ({type(e).__name__}: {e}) — running on sparse (BM25) retrieval only.")
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=5107, debug=True)
