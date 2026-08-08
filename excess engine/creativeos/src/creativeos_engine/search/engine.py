"""The Search Engine — hybrid retrieval over the Creative Knowledge Graph.

*"Retrieval serves reasoning. Reasoning does not serve retrieval."*

Four ways of finding things, because a graph makes questions possible that
keyword search alone cannot answer:

* **keyword**  — TF-IDF over names and facts (`index.py`)
* **relationship** — everything connected to X, optionally by a named predicate
* **traversal** — everything within N hops of X, with the path that got there
* **timeline** — everything true during a window of valid time

The last three are the reason a graph earns its cost. "Who is connected to
Aldric within two steps?" is not a text query at any depth of cleverness.
Semantic (embedding) search is deliberately absent: it needs a model, and every
question asked so far is answerable without one.
"""

from collections import deque

from .index import SearchIndex


class Hit:
    """One search result, carrying why it matched."""

    __slots__ = ("entity", "score", "how", "path", "via")

    def __init__(self, entity, score, how, path=None, via=None):
        self.entity = entity
        self.score = score
        self.how = how          # "keyword" | "relationship" | "traversal" | "timeline"
        self.path = path or []  # entity ids walked to reach this, for traversal
        self.via = via          # the predicate that connected it, if any

    def describe(self):
        detail = f" via {self.via}" if self.via else ""
        hops = f" ({len(self.path) - 1} hops)" if len(self.path) > 1 else ""
        return f"{self.entity.name} [{self.how}{detail}{hops}] {self.score}"

    def __repr__(self):
        return f"<Hit {self.describe()}>"


class SearchEngine:
    def __init__(self, graph):
        self.graph = graph
        self._indexes = {}

    def index_for(self, space_id, rebuild=False):
        if rebuild or space_id not in self._indexes:
            self._indexes[space_id] = SearchIndex(self.graph, space_id)
        return self._indexes[space_id]

    def invalidate(self, space_id=None):
        """Drop cached indexes after writes. Callers that write then search in
        one breath should invalidate, or subscribe to the Event Engine and do it
        automatically."""
        if space_id is None:
            self._indexes.clear()
        else:
            self._indexes.pop(space_id, None)

    # -- the four retrieval modes -----------------------------------------

    def keyword(self, space_id, query, limit=10, rebuild=False):
        index = self.index_for(space_id, rebuild=rebuild)
        return [Hit(entity, score, "keyword") for entity, score in index.search(query, limit)]

    def related(self, space_id, entity_id, predicate=None, at=None, as_of=None):
        """Everything directly connected to an entity, optionally by predicate."""
        hits = []
        for assertion, other in self.graph.neighbors(entity_id, at=at, as_of=as_of):
            if predicate is not None and assertion.predicate != predicate:
                continue
            hits.append(Hit(other, round(assertion.confidence, 4), "relationship",
                            path=[entity_id, other.id], via=assertion.predicate))
        return sorted(hits, key=lambda h: (-h.score, h.entity.name))

    def traverse(self, space_id, entity_id, depth=2, at=None, as_of=None):
        """Breadth-first walk out to `depth` hops, nearest first.

        Score falls off with distance so a direct connection outranks a distant
        one, and each hit keeps the path that reached it — a connection you
        cannot explain is not much use to anyone.
        """
        start = self.graph.canonical_id(entity_id)
        seen = {start}
        queue = deque([(start, [start], None)])
        hits = []

        while queue:
            current, path, via = queue.popleft()
            if len(path) - 1 >= depth:
                continue
            for assertion, other in self.graph.neighbors(current, at=at, as_of=as_of):
                if other.id in seen:
                    continue
                seen.add(other.id)
                next_path = path + [other.id]
                hits.append(Hit(other, round(1.0 / len(next_path), 4), "traversal",
                                path=next_path, via=assertion.predicate))
                queue.append((other.id, next_path, assertion.predicate))
        return sorted(hits, key=lambda h: (-h.score, h.entity.name))

    def during(self, space_id, start=None, end=None, predicate=None, as_of=None):
        """Every entity with a **dated** fact true during a window of valid time.

        The timeline question — "who was alive in 1140?", "what was in force
        during the war?" — which needs the two clocks the graph already keeps.

        Only bounded assertions count. An unbounded fact ("always true") makes
        no claim about *when*, so treating it as evidence of presence would
        match every entity in every window and make this useless. A character's
        occupation says nothing about whether they had been born yet; their
        `alive` window does.
        """
        hits = []
        for entity in self.graph.find_entities(space_id):
            matched = None
            for a in self.graph.history_of(entity.id):
                if a.is_retracted:
                    continue
                if predicate is not None and a.predicate != predicate:
                    continue
                if a.valid.start is None and a.valid.end is None:
                    continue  # carries no temporal claim
                if _window_overlaps(a.valid, start, end):
                    matched = a
                    break
            if matched is not None:
                hits.append(Hit(entity, 1.0, "timeline", via=matched.predicate))
        return sorted(hits, key=lambda h: h.entity.name)

    # -- hybrid ------------------------------------------------------------

    def find(self, space_id, query=None, near=None, depth=1, limit=10,
             at=None, as_of=None, rebuild=False):
        """Keyword and graph proximity combined into one ranked list.

        An entity found both ways ranks above one found only by text, because
        matching the words *and* being connected to what was asked about is
        stronger evidence than either alone.
        """
        scores, best = {}, {}

        if query:
            for hit in self.keyword(space_id, query, limit=limit * 2, rebuild=rebuild):
                scores[hit.entity.id] = scores.get(hit.entity.id, 0.0) + hit.score
                best[hit.entity.id] = hit

        if near:
            for hit in self.traverse(space_id, near, depth=depth, at=at, as_of=as_of):
                scores[hit.entity.id] = scores.get(hit.entity.id, 0.0) + hit.score
                if hit.entity.id not in best:
                    best[hit.entity.id] = hit
                else:
                    best[hit.entity.id].how = "keyword+graph"

        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], best[kv[0]].entity.name))
        results = []
        for entity_id, score in ranked[:limit]:
            hit = best[entity_id]
            hit.score = round(score, 4)
            results.append(hit)
        return results


def _window_overlaps(window, start, end):
    if start is None and end is None:
        return True
    if end is not None and window.start is not None and window.start >= end:
        return False
    if start is not None and window.end is not None and window.end <= start:
        return False
    return True
