"""Keyword scoring over the graph — TF-IDF, no dependency, no model.

Constitution v2.0, Search Engine: *"Hybrid search. Semantic. Keyword. Knowledge
graph. Relationship search. Contextual search. Everything searchable."*

This is the keyword half. It scores entities by the words in their name and in
every assertion made about them, which means an entity becomes findable by its
*facts*, not just its label — searching "navigator" finds the character whose
occupation is navigator even though the word appears nowhere in their name.

TF-IDF rather than substring matching because raw frequency over-rewards words
that appear everywhere. In a film space "scene" is in half the records and
carries almost no signal; a rare word like "Ravenmoor" should dominate, and
inverse document frequency is what encodes that.
"""

import math
import re
from collections import Counter

STOPWORDS = set(
    "the a an and or of to in on for with is are was were be been being this "
    "that these those it its as at by from into out over under then than so "
    "such but if how what when where who whom which why do does did done has "
    "have had not no true false unknown".split()
)


def tokenize(text):
    return [t for t in re.findall(r"[a-z0-9]+", str(text).lower())
            if len(t) > 1 and t not in STOPWORDS]


class SearchIndex:
    """A TF-IDF index over entities and the assertions about them.

    Built on demand from the graph rather than maintained incrementally. At this
    scale rebuilding is milliseconds, and an index that cannot go stale is worth
    more than one that is marginally faster — a search that silently misses
    yesterday's facts is worse than no search.
    """

    def __init__(self, graph, space_id):
        self.graph = graph
        self.space_id = space_id
        self.documents = {}   # entity_id -> token list
        self.entities = {}    # entity_id -> Entity
        self._build()

    def _build(self):
        for entity in self.graph.find_entities(self.space_id):
            tokens = tokenize(entity.name) + tokenize(entity.kind)
            if entity.subkind:
                tokens += tokenize(entity.subkind)
            for a in self.graph.history_of(entity.id):
                if a.is_retracted:
                    continue  # retracted facts must not keep an entity findable
                tokens += tokenize(a.predicate)
                if a.object_value:
                    tokens += tokenize(a.object_value)
            self.entities[entity.id] = entity
            self.documents[entity.id] = tokens

        n = len(self.documents) or 1
        df = Counter()
        for tokens in self.documents.values():
            for term in set(tokens):
                df[term] += 1
        self.idf = {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}

        self.vectors = {}
        for entity_id, tokens in self.documents.items():
            if not tokens:
                self.vectors[entity_id] = {}
                continue
            tf = Counter(tokens)
            vec = {t: (c / len(tokens)) * self.idf.get(t, 1.0) for t, c in tf.items()}
            norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
            self.vectors[entity_id] = {t: v / norm for t, v in vec.items()}

    def search(self, query, limit=10):
        """`[(entity, score), ...]`, best first. Empty when nothing matches —
        never a shrug of low-scoring noise."""
        terms = tokenize(query)
        if not terms:
            return []
        tf = Counter(terms)
        q = {t: (c / len(terms)) * self.idf.get(t, math.log(2) + 1)
             for t, c in tf.items()}
        norm = math.sqrt(sum(v * v for v in q.values())) or 1.0
        q = {t: v / norm for t, v in q.items()}

        scored = []
        for entity_id, vec in self.vectors.items():
            if not vec:
                continue
            small, large = (q, vec) if len(q) <= len(vec) else (vec, q)
            score = sum(v * large.get(t, 0.0) for t, v in small.items())
            if score > 0:
                scored.append((self.entities[entity_id], round(score, 4)))
        scored.sort(key=lambda pair: (-pair[1], pair[0].name))
        return scored[:limit]
