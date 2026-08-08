"""ContextCoreEngine — the single entry point tying chunking, retrieval, confidence,
generation, and the graph together. No Flask, no HTTP, no templates: this is what a UI
(web, CLI, or otherwise) sits on top of.
"""

import uuid
from datetime import datetime, timezone

from . import generation, graph
from .chunking import chunk_text
from .confidence import assess_confidence
from .retrieval import TFIDFIndex
from .store import Store


class AskResult:
    def __init__(self, answer, mode, note, citations, confidence, conflict=None, conflict_note=None):
        self.answer = answer
        self.mode = mode
        self.note = note
        self.citations = citations
        self.confidence = confidence
        self.conflict = conflict
        self.conflict_note = conflict_note

    def to_dict(self):
        return {
            "answer": self.answer, "mode": self.mode, "note": self.note,
            "citations": self.citations, "confidence": self.confidence,
            "conflict": self.conflict, "conflict_note": self.conflict_note,
        }


class ContextCoreEngine:
    def __init__(self, db_path=":memory:", api_key=None, top_k=4):
        self.store = Store(db_path)
        self.api_key = api_key
        self.top_k = top_k

    def ingest_document(self, title, text, category="general", extract_entities=True):
        """Chunk, index, persist, and (if a key is available) extract entities/relationships.
        Returns doc_id, or None if the text produced no chunks.
        """
        chunks = chunk_text(text)
        if not chunks:
            return None

        doc_id = "CX-" + uuid.uuid4().hex[:10].upper()
        self.store.add_document(doc_id, title, category, datetime.now(timezone.utc).isoformat())
        self.store.add_chunks(doc_id, chunks)
        self.store.commit()

        entity_count = rel_count = 0
        extraction_note = None
        if extract_entities:
            entities, relationships, extraction_note = generation.extract_entities_relationships(
                text, api_key=self.api_key
            )
            entity_count, rel_count = self.store.add_entities_relationships(doc_id, entities, relationships)
            self.store.commit()

        return {
            "doc_id": doc_id, "chunk_count": len(chunks),
            "entity_count": entity_count, "relationship_count": rel_count,
            "extraction_note": extraction_note,
        }

    def ask(self, doc_id, question):
        chunks = self.store.load_chunks(doc_id)
        return self._ask_over(question, chunks, [None] * len(chunks))

    def ask_collection(self, category, question):
        pooled = self.store.load_collection_chunks(category)
        texts = [c["text"] for c in pooled]
        sources = [c["title"] for c in pooled]
        result = self._ask_over(question, texts, sources, with_conflict=True)
        for c, pooled_item in zip(result.citations, [pooled[i] for i, _ in self._last_hits]):
            c["doc_title"] = pooled_item["title"]
            c["doc_id"] = pooled_item["doc_id"]
        return result

    def _ask_over(self, question, chunks, sources, with_conflict=False):
        index = TFIDFIndex(chunks)
        hits = index.search(question, k=self.top_k)
        self._last_hits = hits
        passages = [(i, chunks[i]) for i, _ in hits]
        answer, mode, note = generation.generate_answer(question, passages, api_key=self.api_key)
        confidence = assess_confidence(hits)

        conflict = conflict_note = None
        if with_conflict:
            conflict, conflict_note = generation.detect_conflict(
                question, [(chunks[i], sources[i]) for i, _ in hits], api_key=self.api_key
            )

        citations = [{
            "chunk": i + 1,
            "score": round(score, 3),
            "preview": chunks[i][:220] + ("…" if len(chunks[i]) > 220 else ""),
        } for i, score in hits]

        return AskResult(answer, mode, note, citations, confidence, conflict, conflict_note)

    def graph_for(self, doc_ids):
        """doc_ids: list of document ids to pool into one graph. Returns (nodes, edges, svg)."""
        entities, relationships = self.store.load_graph_data(doc_ids)
        nodes, edges = graph.build_graph(entities, relationships)
        svg = graph.graph_svg(nodes, edges)
        return nodes, edges, svg

    def list_documents(self, category="general"):
        return self.store.list_documents(category)

    def close(self):
        self.store.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
