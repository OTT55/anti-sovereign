"""Phases 5–7 — Context, Reasoning and Verification over a document corpus.

CreativeOS has engines by these names, but they reason over an *entity graph*.
ContextCore's subject is different — a corpus of documents and the passages in
them — so the questions are different too:

* **Context** (Phase 5): assemble passages for a question and *budget* them,
  because a context window is finite and the cut has to be principled.
* **Reasoning** (Phase 6): multi-hop. The question ContextCore exists for and
  cannot currently answer is *"what changed between these documents"*, which no
  single passage contains — it needs two retrievals and a comparison.
* **Verification** (Phase 7): ambiguity, and a **reasoning path** — the ordered
  record of which passages produced an answer, so a reader can audit it instead
  of trusting it.

Deterministic throughout. Where a genuine judgement is needed the constitution
already put that behind the Claude-gated layer in `generation.py`, which
degrades honestly; nothing here fabricates.
"""

from collections import defaultdict

from .ingestion import diff_summary, similarity
from .retrieval import TFIDFIndex


# --------------------------------------------------------------------------
# Phase 5 — Context assembly and budgeting
# --------------------------------------------------------------------------

class Passage:
    """One retrieved chunk, with everything needed to judge and cite it."""

    __slots__ = ("text", "doc_id", "doc_title", "chunk", "score", "size")

    def __init__(self, text, doc_id=None, doc_title=None, chunk=0, score=0.0):
        self.text = text
        self.doc_id = doc_id
        self.doc_title = doc_title
        self.chunk = chunk
        self.score = score
        self.size = len(text)

    def cite(self):
        where = self.doc_title or self.doc_id or "unknown"
        return f"[{where} · chunk {self.chunk + 1}]"

    def __repr__(self):
        return f"<Passage {self.cite()} {self.score:.3f}>"


class Context:
    """Assembled passages, and an honest account of what was cut."""

    def __init__(self, question, passages, dropped, budget):
        self.question = question
        self.passages = passages
        self.dropped = dropped
        self.budget = budget

    @property
    def size(self):
        return sum(p.size for p in self.passages)

    @property
    def sources(self):
        return sorted({p.doc_title or p.doc_id for p in self.passages if p.doc_id})

    def render(self):
        lines = []
        if self.question:
            lines += [f"Question: {self.question}", ""]
        for p in self.passages:
            lines.append(f"{p.cite()} {p.text}")
        if self.dropped:
            lines += ["", f"({len(self.dropped)} lower-scoring passages omitted for space)"]
        return "\n".join(lines).strip()

    def summary(self):
        return {"passages": len(self.passages), "dropped": len(self.dropped),
                "size": self.size, "budget": self.budget, "sources": len(self.sources)}


def assemble(question, passages, budget=2000, per_source_cap=None):
    """Fit retrieved passages to a budget, best first.

    `per_source_cap` limits how many passages any one document may contribute.
    Without it a single long document crowds out every other source, and an
    answer drawn from one document dressed up as a corpus-wide finding is
    misleading — the *spread* of agreement is part of the evidence.
    """
    ranked = sorted(passages, key=lambda p: (-p.score, p.doc_id or "", p.chunk))
    kept, dropped, used = [], [], 0
    per_source = defaultdict(int)

    for p in ranked:
        if per_source_cap is not None and per_source[p.doc_id] >= per_source_cap:
            dropped.append(p)
            continue
        if used + p.size <= budget:
            kept.append(p)
            used += p.size
            per_source[p.doc_id] += 1
        else:
            dropped.append(p)
    return Context(question, kept, dropped, budget)


# --------------------------------------------------------------------------
# Phase 6 — Multi-hop reasoning
# --------------------------------------------------------------------------

class Comparison:
    """What two documents say about the same question, and how they differ."""

    __slots__ = ("question", "left", "right", "left_passages", "right_passages",
                 "agreement", "only_left", "only_right")

    def __init__(self, question, left, right, left_passages, right_passages,
                 agreement, only_left, only_right):
        self.question = question
        self.left = left
        self.right = right
        self.left_passages = left_passages
        self.right_passages = right_passages
        self.agreement = agreement
        self.only_left = only_left
        self.only_right = only_right

    @property
    def differs(self):
        return bool(self.only_left or self.only_right)

    def describe(self):
        if not self.differs:
            return f"{self.left} and {self.right} say the same thing about this."
        return (f"{self.left} and {self.right} differ: "
                f"{len(self.only_left)} statement(s) only in the first, "
                f"{len(self.only_right)} only in the second.")

    def render(self):
        lines = [self.describe(), ""]
        if self.only_left:
            lines.append(f"Only in {self.left}:")
            lines += [f"  - {s}" for s in self.only_left]
        if self.only_right:
            lines.append(f"Only in {self.right}:")
            lines += [f"  - {s}" for s in self.only_right]
        return "\n".join(lines).strip()


def compare_documents(question, left_label, left_text, right_label, right_text, k=4):
    """*"What changed between these two documents?"* — the multi-hop question.

    Two retrievals and a comparison. No single passage contains this answer,
    which is exactly why single-shot retrieval cannot produce it, and why this
    is the capability the constitution calls out as missing.

    Retrieval is scoped to the *question* rather than diffing whole documents:
    a full diff of two contracts is thousands of lines and answers nothing.
    """
    from .chunking import chunk_text

    left_chunks = chunk_text(left_text) or [left_text]
    right_chunks = chunk_text(right_text) or [right_text]

    left_hits = TFIDFIndex(left_chunks).search(question, k=k)
    right_hits = TFIDFIndex(right_chunks).search(question, k=k)

    left_passages = [Passage(left_chunks[i], left_label, left_label, i, s) for i, s in left_hits]
    right_passages = [Passage(right_chunks[i], right_label, right_label, i, s) for i, s in right_hits]

    diff = diff_summary(" ".join(p.text for p in left_passages),
                        " ".join(p.text for p in right_passages))
    return Comparison(question, left_label, right_label, left_passages, right_passages,
                      agreement=diff["similarity"],
                      only_left=diff["removed"], only_right=diff["added"])


def trace(question, corpus, k=4, hops=2):
    """Follow a question across documents, hop by hop.

    Each hop re-queries using the *best passage of the previous hop* as the new
    query. That is what makes it multi-hop rather than a wider single search:
    a document never mentioning the original terms but discussing what the
    first hop found is reachable this way and by no amount of top-k widening.

    `corpus` is `[{"doc_id", "title", "chunks"}, ...]`.
    """
    flat, owners = [], []
    for doc in corpus:
        for i, chunk in enumerate(doc["chunks"]):
            flat.append(chunk)
            owners.append((doc["doc_id"], doc.get("title"), i))

    if not flat:
        return []

    index = TFIDFIndex(flat)
    path, query, seen = [], question, set()

    for hop in range(hops):
        hits = [(i, s) for i, s in index.search(query, k=k) if i not in seen]
        if not hits:
            break
        passages = []
        for i, score in hits:
            seen.add(i)
            doc_id, title, chunk = owners[i]
            passages.append(Passage(flat[i], doc_id, title, chunk, score))
        path.append({"hop": hop + 1, "query": query, "passages": passages})
        query = passages[0].text[:300]   # the best passage becomes the next query
    return path


# --------------------------------------------------------------------------
# Phase 7 — Verification: ambiguity and the reasoning path
# --------------------------------------------------------------------------

def ambiguous_terms(question, passages, threshold=0.25):
    """Query terms that pull in passages with little in common.

    Distinct from a contradiction: nothing here disagrees, the *question* is
    unclear. "Tell me about the Accord" is ambiguous when the corpus holds
    three unrelated accords, and answering as if there were one is wrong
    without being detectably false.
    """
    if len(passages) < 2:
        return []
    texts = [p.text for p in passages]
    scores = [similarity(a, b) for i, a in enumerate(texts) for b in texts[i + 1:]]
    if not scores:
        return []
    spread = sum(scores) / len(scores)
    if spread >= threshold:
        return []
    return [{
        "question": question,
        "reason": f"the {len(passages)} best passages have little in common "
                  f"(average overlap {spread:.2f})",
        "candidates": sorted({p.doc_title or p.doc_id for p in passages if p.doc_id}),
    }]


class ReasoningPath:
    """The ordered record of how an answer was reached.

    Not decoration — this is the difference between an answer a reader can
    audit and one they must trust. Every step names what was done and what it
    produced, so a wrong answer can be traced to the step that went wrong.
    """

    def __init__(self):
        self.steps = []

    def add(self, action, detail, produced=None):
        self.steps.append({"step": len(self.steps) + 1, "action": action,
                           "detail": detail, "produced": produced})
        return self

    def render(self):
        return "\n".join(
            f"{s['step']}. {s['action']} — {s['detail']}"
            + (f" → {s['produced']}" if s["produced"] else "")
            for s in self.steps)

    def __len__(self):
        return len(self.steps)


def verify_answer(question, passages, answer_text):
    """Check an answer against the passages it claims to rest on.

    The failure this catches is the one that matters most for a citing system:
    an answer that is *plausible* but rests on nothing retrieved. It cannot
    judge truth — it checks grounding, which is a different and computable
    question.
    """
    path = ReasoningPath()
    path.add("retrieve", f"{len(passages)} passage(s) for {question!r}",
             ", ".join(p.cite() for p in passages) or "nothing")

    if not passages:
        path.add("verify", "no passages retrieved", "ungrounded")
        return {"grounded": False, "overlap": 0.0, "sources": [],
                "ambiguity": [], "path": path,
                "note": "Nothing was retrieved, so this answer rests on nothing."}

    corpus = " ".join(p.text for p in passages)
    overlap = similarity(answer_text, corpus)
    ambiguity = ambiguous_terms(question, passages)

    path.add("compare", "answer against retrieved passages", f"overlap {overlap:.2f}")
    if ambiguity:
        path.add("flag", ambiguity[0]["reason"], "ambiguous question")

    grounded = overlap > 0.0
    return {
        "grounded": grounded,
        "overlap": round(overlap, 4),
        "sources": sorted({p.doc_title or p.doc_id for p in passages if p.doc_id}),
        "ambiguity": ambiguity,
        "path": path,
        "note": None if grounded else
                "The answer shares no wording with any retrieved passage — it may "
                "not be supported by the corpus.",
    }
