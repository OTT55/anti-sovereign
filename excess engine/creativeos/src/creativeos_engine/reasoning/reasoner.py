"""The Reasoning Engine — *"Never acts as simple retrieval."*

Constitution v2.0: *"Finds implications. Discovers relationships. Predicts
consequences. Builds recommendations."*

The distinction from Search matters. Search answers "what is connected to X".
Reasoning answers "what *follows* from X" — which requires combining several
facts that no single record contains. Four capabilities, all deterministic:

* **paths** — how two entities are connected, and by what chain. Not "are they
  connected" but the actual route, because the route is the explanation.
* **implications** — facts that follow from transitive relationships. If A is
  part of B and B is part of C, then A is part of C, and nobody asserted it.
* **impact** — what breaks if an entity is removed. Answers "what depends on
  this", which is the question behind every risky change.
* **gaps** — what is conspicuously missing. Something every comparable entity
  has and this one does not is a hole worth naming.

No model. Every conclusion carries the facts that produced it, because a
conclusion you cannot trace is not reasoning — it is assertion.
"""

from collections import defaultdict, deque

#: Predicates that chain: if A→B and B→C hold, A→C holds too. Transitivity is a
#: property of the *predicate*, not of the graph, so it is declared rather than
#: assumed — "part_of" chains, "rival_of" emphatically does not.
TRANSITIVE = {
    "part_of", "member_of", "located_in", "contained_in", "owns", "controls",
    "descended_from", "derived_from", "succeeded_by", "reports_to",
}

#: Predicates where A→B implies B→A.
SYMMETRIC = {
    "allied_with", "married_to", "rival_of", "sibling_of", "knows",
    "related_to", "adjacent_to", "met",
}


class Path:
    """A route between two entities, with the predicates that link it."""

    __slots__ = ("entities", "predicates")

    def __init__(self, entities, predicates):
        self.entities = entities
        self.predicates = predicates

    @property
    def length(self):
        return len(self.predicates)

    def describe(self):
        parts = [self.entities[0].name]
        for predicate, entity in zip(self.predicates, self.entities[1:]):
            parts.append(f"--{predicate}-->")
            parts.append(entity.name)
        return " ".join(parts)

    def __repr__(self):
        return f"<Path {self.describe()}>"


class Implication:
    """A fact that follows from others without anyone asserting it."""

    __slots__ = ("subject", "predicate", "target", "because", "confidence")

    def __init__(self, subject, predicate, target, because, confidence):
        self.subject = subject
        self.predicate = predicate
        self.target = target
        self.because = because      # the assertions it was derived from
        self.confidence = confidence

    def describe(self):
        return (f"{self.subject.name} {self.predicate} {self.target.name} "
                f"(implied, {self.confidence:.2f})")

    def __repr__(self):
        return f"<Implication {self.describe()}>"


class Impact:
    """What removing an entity would disturb."""

    __slots__ = ("entity", "direct", "indirect", "orphaned", "implications_lost")

    def __init__(self, entity, direct, indirect, orphaned, implications_lost):
        self.entity = entity
        self.direct = direct
        self.indirect = indirect
        self.orphaned = orphaned
        self.implications_lost = implications_lost

    @property
    def severity(self):
        """A blunt but honest ranking: things left with no connections at all
        matter more than things that merely lose one."""
        return len(self.direct) + 2 * len(self.orphaned)

    def describe(self):
        return (f"Removing {self.entity.name}: {len(self.direct)} direct, "
                f"{len(self.indirect)} indirect, {len(self.orphaned)} orphaned")

    def summary(self):
        return {
            "entity": self.entity.name,
            "direct": [e.name for e in self.direct],
            "indirect": [e.name for e in self.indirect],
            "orphaned": [e.name for e in self.orphaned],
            "implications_lost": len(self.implications_lost),
            "severity": self.severity,
        }


class Gap:
    """Something conspicuously absent."""

    __slots__ = ("entity", "missing", "reason", "peers_with_it")

    def __init__(self, entity, missing, reason, peers_with_it=0):
        self.entity = entity
        self.missing = missing
        self.reason = reason
        self.peers_with_it = peers_with_it

    def describe(self):
        return f"{self.entity.name} has no {self.missing} — {self.reason}"

    def __repr__(self):
        return f"<Gap {self.describe()}>"


class ReasoningEngine:
    def __init__(self, graph):
        self.graph = graph

    # -- paths -------------------------------------------------------------

    def paths_between(self, from_id, to_id, max_depth=4, limit=5, at=None, as_of=None):
        """Every route between two entities, shortest first.

        Breadth-first so the first routes found are the shortest, which are also
        the most explanatory — a six-hop connection between two characters is
        usually coincidence rather than meaning.
        """
        start = self.graph.canonical_id(from_id)
        target = self.graph.canonical_id(to_id)
        if start == target:
            return []

        found = []
        queue = deque([(start, [start], [])])
        while queue and len(found) < limit:
            current, entities, predicates = queue.popleft()
            if len(predicates) >= max_depth:
                continue
            for assertion, other in self.graph.neighbors(current, at=at, as_of=as_of):
                if other.id in entities:
                    continue  # no cycles
                next_entities = entities + [other.id]
                next_predicates = predicates + [assertion.predicate]
                if other.id == target:
                    found.append(Path(
                        [self.graph.get_entity(e) for e in next_entities],
                        next_predicates))
                    if len(found) >= limit:
                        break
                else:
                    queue.append((other.id, next_entities, next_predicates))
        return sorted(found, key=lambda p: p.length)

    def connected(self, from_id, to_id, max_depth=4):
        return bool(self.paths_between(from_id, to_id, max_depth=max_depth, limit=1))

    # -- implications ------------------------------------------------------

    def implications(self, space_id, at=None, as_of=None):
        """Facts that follow from the graph without being asserted.

        Only for predicates declared transitive or symmetric. Confidence is the
        product of the links, so a chain is never more certain than its weakest
        step — inference should decay, not accumulate certainty it never had.
        """
        out = []
        entities = self.graph.find_entities(space_id)
        by_id = {e.id: e for e in entities}

        edges = defaultdict(list)   # (subject_id, predicate) -> [(target_id, confidence)]
        asserted = set()
        for entity in entities:
            for a in self.graph.history_of(entity.id):
                if a.is_retracted or a.object_id is None:
                    continue
                edges[(a.subject_id, a.predicate)].append((a.object_id, a.confidence, a))
                asserted.add((a.subject_id, a.predicate, a.object_id))

        for (subject_id, predicate), targets in list(edges.items()):
            if predicate in SYMMETRIC:
                for target_id, confidence, assertion in targets:
                    if (target_id, predicate, subject_id) in asserted:
                        continue
                    subject, target = by_id.get(subject_id), by_id.get(target_id)
                    if subject and target:
                        out.append(Implication(target, predicate, subject,
                                               [assertion], confidence))

            if predicate in TRANSITIVE:
                for mid_id, c1, a1 in targets:
                    for end_id, c2, a2 in edges.get((mid_id, predicate), []):
                        if end_id == subject_id:
                            continue
                        if (subject_id, predicate, end_id) in asserted:
                            continue
                        subject, end = by_id.get(subject_id), by_id.get(end_id)
                        if subject and end:
                            out.append(Implication(subject, predicate, end,
                                                   [a1, a2], round(c1 * c2, 4)))

        return sorted(out, key=lambda i: (-i.confidence, i.subject.name))

    # -- impact ------------------------------------------------------------

    def impact_of_removing(self, entity_id, at=None, as_of=None, implications=None):
        """What would be disturbed if this entity went away.

        The question behind every risky change: what depends on this? Orphans —
        things left with no connections at all — are weighted double, because
        losing one edge is inconvenient and losing your last one is disappearing.

        `implications` lets a caller computing *many* impacts pass the space's
        implications in once. Without it every call recomputes them across the
        whole space, which makes a loop over n entities O(n²) — measured at
        4.65s for 400 entities and rising as the square, so ~2 minutes at 2000.
        A single impact can still be asked for on its own; it simply pays for
        the scan itself.
        """
        entity = self.graph.get_entity(entity_id)
        if entity is None:
            return None

        direct, indirect, orphaned = [], [], []
        for _assertion, other in self.graph.neighbors(entity_id, at=at, as_of=as_of):
            if other.id in {e.id for e in direct}:
                continue
            direct.append(other)
            remaining = [o for _a, o in self.graph.neighbors(other.id, at=at, as_of=as_of)
                         if o.id != entity.id]
            if not remaining:
                orphaned.append(other)

        direct_ids = {e.id for e in direct} | {entity.id}
        for neighbour in direct:
            for _a, other in self.graph.neighbors(neighbour.id, at=at, as_of=as_of):
                if other.id not in direct_ids and other.id not in {e.id for e in indirect}:
                    indirect.append(other)

        if implications is None:
            implications = self.implications(entity.space_id, at=at, as_of=as_of)
        lost = [i for i in implications
                if entity.id in (i.subject.id, i.target.id)]

        return Impact(entity, direct, indirect, orphaned, lost)

    # -- gaps --------------------------------------------------------------

    def gaps(self, space_id, min_peers=2, at=None, as_of=None):
        """What is conspicuously missing.

        Not everything absent — only what *comparable* entities have. If every
        other character has a birth date and this one does not, that is a hole
        worth naming; if nobody has one, it is simply not how this space is
        recorded, and nagging about it would be noise.
        """
        by_kind = defaultdict(list)
        predicates = defaultdict(lambda: defaultdict(set))

        for entity in self.graph.find_entities(space_id):
            by_kind[entity.kind].append(entity)
            for a in self.graph.history_of(entity.id):
                if not a.is_retracted:
                    predicates[entity.kind][a.predicate].add(entity.id)

        out = []
        for kind, entities in by_kind.items():
            if len(entities) < min_peers + 1:
                continue
            for predicate, holders in predicates[kind].items():
                if len(holders) < min_peers:
                    continue
                # Common enough among peers that its absence is notable.
                if len(holders) / len(entities) < 0.5:
                    continue
                for entity in entities:
                    if entity.id not in holders:
                        out.append(Gap(
                            entity, predicate,
                            f"{len(holders)} of {len(entities)} other {kind}s have one",
                            peers_with_it=len(holders)))
        return sorted(out, key=lambda g: (-g.peers_with_it, g.entity.name, g.missing))
