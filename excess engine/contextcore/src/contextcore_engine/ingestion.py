"""Phase 2 — the Ingestion Engine, completed.

Parsing and chunking already worked. What was missing is everything that
decides *whether a document should be ingested at all, and what it is*:

* **Duplicate detection** — the same bytes ingested twice is one document, not
  two. Without this a corpus silently doubles every time someone re-uploads a
  folder, and every retrieval score is then distorted by the copies.
* **Version detection** — the harder and more valuable case. The same document
  *slightly edited* is not a duplicate and not an unrelated document: it is
  version 2, and knowing that is what makes "what changed between drafts"
  answerable at all.
* **Metadata** — filename, size, ingest time, so a chunk can always be traced
  back to where it came from.
* **Language detection** — by stopword overlap, no ML dependency. Retrieval is
  English-tuned (the stopword list, the tokenizer), so a French document
  silently scoring badly is worth knowing about rather than discovering later.

All deterministic, no API key, no external dependency.
"""

import hashlib
import re
from collections import Counter

#: The most frequent words in each language. Overlap with a document's most
#: frequent words identifies it — crude, but it needs no model and no download,
#: and it only has to be right enough to warn.
STOPWORD_SETS = {
    "en": {"the", "of", "and", "to", "in", "a", "is", "that", "for", "it",
           "with", "as", "was", "on", "be", "by", "this", "are", "from", "at"},
    "fr": {"le", "de", "et", "la", "les", "des", "un", "une", "du", "que",
           "est", "pour", "dans", "qui", "sur", "pas", "au", "ce", "il", "en"},
    "es": {"el", "de", "la", "que", "y", "en", "los", "un", "por", "las",
           "con", "una", "para", "es", "del", "se", "no", "su", "al", "lo"},
    "de": {"der", "die", "und", "den", "von", "zu", "das", "mit", "sich",
           "des", "auf", "für", "ist", "im", "dem", "nicht", "ein", "eine"},
    "pt": {"de", "que", "não", "os", "para", "com", "uma", "por", "mais",
           "das", "como", "mas", "ao", "dos", "mesmo", "pelo", "até", "isso"},
}

#: Similarity above which two documents of the same title are versions of each
#: other rather than different documents. Deliberately high: calling two
#: unrelated papers "versions" corrupts the history, which is worse than
#: missing a link a human can add.
VERSION_THRESHOLD = 0.6


def content_hash(text):
    """SHA-256 of the normalised text.

    Normalised so that a re-export differing only in line endings or trailing
    whitespace is still recognised as the same document — which it is.
    """
    normalised = re.sub(r"\s+", " ", (text or "").strip()).encode("utf-8")
    return hashlib.sha256(normalised).hexdigest()


def shingles(text, size=5):
    """Overlapping word n-grams — the unit similarity is measured in.

    Word-level rather than character-level: most shingles sit *inside* a
    paragraph, so moving whole paragraphs breaks only the few that straddle
    the joins, and a reordered document still reads as a version (~0.79 on
    real prose).

    The honest limit: when sentences are shorter than `size`, nearly every
    shingle straddles a boundary and reordering destroys them. Terse,
    list-like text will therefore under-report similarity and its versions may
    be missed. Both behaviours are pinned by tests.
    """
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    if len(words) < size:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + size]) for i in range(len(words) - size + 1)}


def similarity(left, right):
    """Jaccard similarity of two texts' shingles, 0.0–1.0.

    Jaccard rather than cosine because the question here is "how much of this
    document is the same document", which is a set-overlap question, not an
    angle between weighted vectors.
    """
    a, b = shingles(left), shingles(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def detect_language(text, minimum=0.02):
    """`(code, confidence)` — best-guess language and how sure.

    Returns `("unknown", 0.0)` rather than defaulting to English when nothing
    scores, because "we could not tell" and "it is English" are different
    claims and only one of them is honest.
    """
    words = re.findall(r"[a-zà-ÿ]+", (text or "").lower())
    if not words:
        return "unknown", 0.0
    counts = Counter(words)
    total = sum(counts.values())

    scored = []
    for code, stopwords in STOPWORD_SETS.items():
        hits = sum(counts[w] for w in stopwords if w in counts)
        scored.append((hits / total, code))
    scored.sort(reverse=True)

    best_score, best_code = scored[0]
    if best_score < minimum:
        return "unknown", round(best_score, 4)
    return best_code, round(best_score, 4)


def extract_metadata(title, text, filename=None, media_type=None):
    """What is worth recording about a document beyond its text."""
    language, confidence = detect_language(text)
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {
        "title": title,
        "filename": filename,
        "media_type": media_type,
        "bytes": len((text or "").encode("utf-8")),
        "words": len(words),
        "content_hash": content_hash(text),
        "language": language,
        "language_confidence": confidence,
    }


class IngestDecision:
    """What ingestion concluded about a document, and why.

    Carrying the reason matters: "this was skipped" and "this was skipped
    because byte-identical content is already stored as CX-ABC" are very
    different messages to show a user who expected their upload to appear.
    """

    __slots__ = ("action", "reason", "existing_doc_id", "similarity", "metadata")

    def __init__(self, action, reason, existing_doc_id=None, similarity=0.0, metadata=None):
        self.action = action          # "ingest" | "duplicate" | "version"
        self.reason = reason
        self.existing_doc_id = existing_doc_id
        self.similarity = similarity
        self.metadata = metadata or {}

    @property
    def is_new(self):
        return self.action == "ingest"

    def describe(self):
        return f"{self.action}: {self.reason}"

    def __repr__(self):
        return f"<IngestDecision {self.describe()}>"


def classify_incoming(title, text, existing, filename=None, media_type=None):
    """Decide whether an incoming document is new, a duplicate, or a version.

    `existing` is `[{"doc_id", "title", "content_hash", "text"}, ...]`.

    Order matters: an exact hash match is checked first because it is certain
    and cheap, and only then the expensive similarity pass. A document that is
    byte-identical to an existing one is never worth comparing further.
    """
    metadata = extract_metadata(title, text, filename=filename, media_type=media_type)
    incoming_hash = metadata["content_hash"]

    for doc in existing:
        if doc.get("content_hash") == incoming_hash:
            return IngestDecision(
                "duplicate",
                f"identical content is already stored as {doc['doc_id']}",
                existing_doc_id=doc["doc_id"], similarity=1.0, metadata=metadata)

    # A version has to share a title *and* most of its text. Title alone
    # catches unrelated documents people happen to name "Report"; similarity
    # alone links a boilerplate contract to every other contract.
    best = None
    for doc in existing:
        if (doc.get("title") or "").strip().lower() != (title or "").strip().lower():
            continue
        score = similarity(text, doc.get("text", ""))
        if score >= VERSION_THRESHOLD and (best is None or score > best[1]):
            best = (doc, score)

    if best is not None:
        doc, score = best
        return IngestDecision(
            "version",
            f"{int(score * 100)}% of the text matches {doc['doc_id']}, "
            "which has the same title",
            existing_doc_id=doc["doc_id"], similarity=round(score, 4), metadata=metadata)

    return IngestDecision("ingest", "new document", metadata=metadata)


def diff_summary(old_text, new_text):
    """What changed between two versions, in plain terms.

    Sentence-level rather than word-level: a writer asking "what changed"
    wants the sentences that moved, not a character diff.
    """
    def sentences(t):
        return [s.strip() for s in re.split(r"(?<=[.!?])\s+", (t or "").strip()) if s.strip()]

    old, new = sentences(old_text), sentences(new_text)
    old_set, new_set = set(old), set(new)
    return {
        "added": [s for s in new if s not in old_set],
        "removed": [s for s in old if s not in new_set],
        "unchanged": len(old_set & new_set),
        "similarity": round(similarity(old_text, new_text), 4),
    }
