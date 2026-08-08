"""Phase 8 — the Intelligence Engine: the coordinator.

The same six questions CreativeOS's coordinator answers, asked of a *corpus*
rather than an entity graph:

    what exists · what changed · what is connected
    what matters · what is missing · what happens next

It delegates to the engines that own each capability and holds almost no logic
itself — the one exception being **what matters**, which cannot be retrieved
because it is not a property of any document. A document matters in proportion
to how much of the corpus's knowledge only it carries.

That measure is deliberate. Ranking by length rewards padding; ranking by hit
count rewards whatever people happen to search for. Ranking by *unique
contribution* answers the question actually being asked: if this document
vanished, how much would the corpus lose?
"""

from collections import Counter, defaultdict

from . import domain as domain_module
from .ingestion import similarity
from .reasoning import Passage, assemble, compare_documents
from .resolution import Ontology, resolve
from .retrieval import TFIDFIndex


class CorpusBriefing:
    """Everything the Intelligence Engine has to say about a corpus."""

    def __init__(self, exists, changed, matters, missing, next_up, domain_name):
        self.exists = exists
        self.changed = changed
        self.matters = matters
        self.missing = missing
        self.next_up = next_up
        self.domain_name = domain_name

    def summary(self):
        return {
            "documents": self.exists["documents"],
            "chunks": self.exists["chunks"],
            "entities": self.exists["entities"],
            "languages": self.exists["languages"],
            "key_documents": [name for name, _ in self.matters[:3]],
            "gaps": len(self.missing),
            "recommendations": len(self.next_up),
            "domain": self.domain_name,
        }

    def render(self):
        lines = [f"# Corpus briefing ({self.domain_name})", ""]
        lines.append(f"{self.exists['documents']} document(s), "
                     f"{self.exists['chunks']} chunk(s), "
                     f"{self.exists['entities']} resolved entity(ies)")
        if self.exists["languages"] and self.exists["languages"] != ["en"]:
            lines.append(f"Languages present: {', '.join(self.exists['languages'])}")
        lines.append("")

        if self.matters:
            lines.append("## What matters")
            for name, score in self.matters[:5]:
                lines.append(f"- {name} ({score:.2f})")
            lines.append("")
        if self.missing:
            lines.append("## What is missing")
            for gap in self.missing[:5]:
                lines.append(f"- {gap['title'] or gap['doc_id']}: {gap['note']}")
            lines.append("")
        if self.next_up:
            lines.append("## What to do next")
            lines += [f"- {r}" for r in self.next_up[:5]]
        return "\n".join(lines).strip()


class IntelligenceEngine:
    """Coordinates the corpus engines. Holds almost no logic of its own."""

    def __init__(self, documents, domain="general"):
        """`documents` is `[{"doc_id","title","text","chunks","language","fields"}, ...]`."""
        self.documents = list(documents)
        self.domain = domain_module.get(domain)
        self._ontology = None

    # -- the six questions -------------------------------------------------

    def what_exists(self):
        chunks = sum(len(d.get("chunks") or []) for d in self.documents)
        languages = sorted({d.get("language") or "unknown" for d in self.documents})
        return {
            "documents": len(self.documents),
            "chunks": chunks,
            "entities": len(self.ontology().entities),
            "languages": languages,
            "titles": sorted(d.get("title", "") for d in self.documents),
        }

    def what_changed(self, memory=None):
        """Version history, from the Memory Engine when one is supplied."""
        if memory is None:
            return []
        out = []
        for doc in self.documents:
            chain = memory.chain(doc["doc_id"])
            if len(chain) > 1:
                out.append({
                    "doc_id": doc["doc_id"], "title": doc.get("title"),
                    "versions": len(chain),
                    "closed_facts": len(memory.closed_facts(doc["doc_id"])),
                })
        return out

    def what_is_connected(self, doc_id, threshold=0.15):
        """Documents sharing substantial wording with this one."""
        target = next((d for d in self.documents if d["doc_id"] == doc_id), None)
        if target is None:
            return []
        out = []
        for other in self.documents:
            if other["doc_id"] == doc_id:
                continue
            score = similarity(target.get("text", ""), other.get("text", ""))
            if score >= threshold:
                out.append({"doc_id": other["doc_id"], "title": other.get("title"),
                            "similarity": round(score, 4)})
        return sorted(out, key=lambda d: -d["similarity"])

    def what_matters(self, limit=10):
        """Rank documents by how much of the corpus's knowledge only they carry.

        Length rewards padding and hit counts reward whatever people search
        for. Unique contribution answers the real question: if this vanished,
        how much would the corpus lose?
        """
        if not self.documents:
            return []

        term_docs = defaultdict(set)
        per_doc = {}
        for doc in self.documents:
            terms = _terms(doc.get("text", ""))
            per_doc[doc["doc_id"]] = terms
            for term in terms:
                term_docs[term].add(doc["doc_id"])

        scored = []
        for doc in self.documents:
            terms = per_doc[doc["doc_id"]]
            if not terms:
                scored.append((doc.get("title") or doc["doc_id"], 0.0))
                continue
            unique = sum(1 for t in terms if len(term_docs[t]) == 1)
            scored.append((doc.get("title") or doc["doc_id"],
                           round(unique / len(terms), 4)))
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        return scored[:limit]

    def what_is_missing(self):
        """What the *domain* expects and a document does not have."""
        return domain_module.audit(self.domain, self.documents)

    def what_happens_next(self, limit=10):
        """Recommendations, most consequential first.

        Ambiguity outranks absence: a corpus holding two unrelated things under
        one name produces confidently wrong answers, whereas a missing field
        produces an obviously incomplete one. The wrong answer is the more
        expensive failure.
        """
        out = []

        duplicate_titles = [t for t, n in Counter(
            (d.get("title") or "").strip().lower() for d in self.documents).items()
            if t and n > 1]
        for title in duplicate_titles:
            out.append(f"Disambiguate — {n_documents(self.documents, title)} documents "
                       f"share the title '{title}'")

        for gap in self.what_is_missing():
            out.append(f"Fill the gap — {gap['title'] or gap['doc_id']}: {gap['note']}")

        # Any cluster that absorbed another name is worth confirming. A merge
        # is consequential and silent — "Acme Corp" quietly becoming "Acme
        # Corporation" is exactly the decision a human should see once.
        unresolved = [c for c in self.clusters() if c.aliases]
        for cluster in unresolved[:3]:
            out.append(f"Confirm the merge — '{cluster.canonical}' also appears as "
                       f"{', '.join(cluster.aliases[:3])}")

        languages = {d.get("language") for d in self.documents} - {None, "en"}
        if languages:
            out.append(f"Check retrieval quality — {', '.join(sorted(languages))} "
                       "documents are present and retrieval is English-tuned")
        return out[:limit]

    # -- shared machinery --------------------------------------------------

    def clusters(self):
        entities = []
        for doc in self.documents:
            entities += doc.get("entities") or []
        return resolve(entities)

    def ontology(self):
        if self._ontology is None:
            self._ontology = Ontology().learn(self.clusters())
        return self._ontology

    def context_for(self, question, budget=2000, per_source_cap=2):
        """Assemble context for a question across the whole corpus."""
        flat, owners = [], []
        for doc in self.documents:
            for i, chunk in enumerate(doc.get("chunks") or []):
                flat.append(chunk)
                owners.append((doc["doc_id"], doc.get("title"), i))
        if not flat:
            return assemble(question, [], budget=budget)

        hits = TFIDFIndex(flat).search(question, k=12)
        passages = [Passage(flat[i], *owners[i][:2], owners[i][2], score)
                    for i, score in hits]
        return assemble(question, passages, budget=budget, per_source_cap=per_source_cap)

    def compare(self, question, left_id, right_id):
        left = next(d for d in self.documents if d["doc_id"] == left_id)
        right = next(d for d in self.documents if d["doc_id"] == right_id)
        return compare_documents(question, left.get("title") or left_id, left["text"],
                                 right.get("title") or right_id, right["text"])

    def brief(self, memory=None):
        return CorpusBriefing(
            exists=self.what_exists(),
            changed=self.what_changed(memory),
            matters=self.what_matters(),
            missing=self.what_is_missing(),
            next_up=self.what_happens_next(),
            domain_name=self.domain.name,
        )


def _terms(text):
    from .retrieval import tokenize
    return set(tokenize(text))


def n_documents(documents, title):
    return sum(1 for d in documents if (d.get("title") or "").strip().lower() == title)
