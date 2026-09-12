"""The Verification Engine — *"Truth should never be assumed."*

Phase 1 built the floor: two live assertions disagreeing over overlapping valid
windows is a contradiction, found deterministically. This completes the rest of
what the constitution asks for — *"Measures confidence. Detects contradictions.
Tracks evidence. Validates relationships. Surfaces uncertainty."*

Four things the floor did not cover:

* **Evidence** — what actually supports a claim, and how independent that
  support is. Ten repetitions of one rumour is not ten pieces of evidence.
* **Ambiguity** — two different entities a name could equally mean.
* **Relationship validity** — a relationship whose endpoints contradict it,
  such as one asserted during a period when one party did not exist.
* **Uncertainty** — surfaced as a number, with the reason attached.

All deterministic. A verdict you cannot explain is not verification.
"""

from collections import defaultdict


class Evidence:
    """What supports one claim, and how strongly."""

    __slots__ = ("predicate", "value", "assertions", "sources", "score", "subject_id")

    def __init__(self, predicate, value, assertions, subject_id=None):
        self.predicate = predicate
        self.value = value
        self.assertions = assertions
        self.sources = sorted({a.source_kind for a in assertions})
        self.subject_id = subject_id
        self.score = self._score()

    def _score(self):
        """Confidence in this claim, given everything asserting it.

        Independent sources compound; repetition from one source does not. Two
        documents agreeing is real corroboration, whereas the same document
        quoted twice is one claim counted twice — and treating those alike is
        how a rumour becomes a fact.
        """
        if not self.assertions:
            return 0.0
        by_source = defaultdict(list)
        for a in self.assertions:
            by_source[a.source_kind].append(a.confidence)
        # Best claim from each distinct source, combined as independent evidence:
        # 1 - Π(1 - c). Two 0.6 sources give 0.84; one 0.6 source twice gives 0.6.
        remaining = 1.0
        for confidences in by_source.values():
            remaining *= (1.0 - max(confidences))
        return round(1.0 - remaining, 4)

    @property
    def independent_sources(self):
        return len(self.sources)

    def describe(self):
        return (f"{self.predicate} = {self.value} "
                f"({self.score:.2f} from {self.independent_sources} source(s): "
                f"{', '.join(self.sources)})")

    def __repr__(self):
        return f"<Evidence {self.describe()}>"


class Ambiguity:
    """A name that could equally mean more than one entity."""

    __slots__ = ("name", "candidates")

    def __init__(self, name, candidates):
        self.name = name
        self.candidates = candidates

    def describe(self):
        return f"'{self.name}' could mean: " + ", ".join(
            f"{e.name} ({e.kind})" for e in self.candidates)

    def __repr__(self):
        return f"<Ambiguity {self.name}>"


class InvalidRelationship:
    """A relationship its own endpoints do not support."""

    __slots__ = ("assertion", "reason", "subject", "target")

    def __init__(self, assertion, reason, subject=None, target=None):
        self.assertion = assertion
        self.reason = reason
        self.subject = subject
        self.target = target

    def describe(self):
        subject = self.subject.name if self.subject else self.assertion.subject_id
        target = self.target.name if self.target else self.assertion.object_id
        return f"{subject} {self.assertion.predicate} {target}: {self.reason}"

    def __repr__(self):
        return f"<InvalidRelationship {self.describe()}>"


class Verdict:
    """Everything verification has to say about an entity or a space."""

    def __init__(self, evidence=None, contradictions=None, ambiguities=None,
                 invalid_relationships=None, unsupported=None):
        self.evidence = evidence or []
        self.contradictions = contradictions or []
        self.ambiguities = ambiguities or []
        self.invalid_relationships = invalid_relationships or []
        self.unsupported = unsupported or []

    @property
    def is_clean(self):
        return not (self.contradictions or self.ambiguities
                    or self.invalid_relationships or self.unsupported)

    @property
    def certainty(self):
        """One number for "how much should this be trusted", or `None` when
        there is nothing to judge.

        The weakest evidence sets the ceiling — a picture is only as sound as
        its shakiest load-bearing claim — and any contradiction caps it hard,
        because a set of facts that disagree cannot be mostly true.
        """
        if not self.evidence:
            return None
        floor = min(e.score for e in self.evidence)
        if self.contradictions:
            return round(min(floor, 0.4), 4)
        return round(floor, 4)

    def summary(self):
        return {
            "evidence": len(self.evidence),
            "contradictions": len(self.contradictions),
            "ambiguities": len(self.ambiguities),
            "invalid_relationships": len(self.invalid_relationships),
            "unsupported": len(self.unsupported),
            "certainty": self.certainty,
        }


class VerificationEngine:
    def __init__(self, graph):
        self.graph = graph

    # -- evidence ----------------------------------------------------------

    def evidence_for(self, entity_id, predicate=None, as_of=None):
        """What supports each claim about an entity, grouped by claim."""
        grouped = defaultdict(list)
        for a in self.graph.history_of(entity_id):
            if a.is_retracted:
                continue
            if predicate is not None and a.predicate != predicate:
                continue
            grouped[(a.predicate, a.object_repr())].append(a)

        out = [Evidence(pred, value, assertions, subject_id=entity_id)
               for (pred, value), assertions in grouped.items()]
        return sorted(out, key=lambda e: (-e.score, e.predicate))

    def unsupported_claims(self, entity_id, threshold=0.5):
        """Claims resting on evidence too thin to rely on.

        Surfacing these is the point of "never assume truth": a low-confidence
        claim is not an error, but acting on it as though it were certain is.
        """
        return [e for e in self.evidence_for(entity_id) if e.score < threshold]

    # -- ambiguity ---------------------------------------------------------

    def ambiguities(self, space_id):
        """Names that resolve to more than one entity.

        Distinct from a contradiction: nothing here disagrees, it is simply
        unclear which thing is meant — and an answer that silently picks one is
        wrong half the time.
        """
        by_name = defaultdict(list)
        for entity in self.graph.find_entities(space_id):
            by_name[entity.name.strip().lower()].append(entity)

        out = []
        for name, entities in sorted(by_name.items()):
            if len(entities) < 2:
                continue
            # Entities merged into one identity are not ambiguous.
            canonical = {self.graph.canonical_id(e.id) for e in entities}
            if len(canonical) < 2:
                continue
            out.append(Ambiguity(entities[0].name, entities))
        return out

    # -- relationship validity ---------------------------------------------

    def invalid_relationships(self, space_id, as_of=None):
        """Relationships their own endpoints do not support.

        The main case: a relationship asserted over a window when one party did
        not exist — someone serving under a commander a century after that
        commander died. The graph has the lifespans; nothing was checking them
        against the edges.
        """
        out = []
        for entity in self.graph.find_entities(space_id):
            for a in self.graph.history_of(entity.id):
                if a.is_retracted or a.object_id is None:
                    continue
                if a.valid.start is None and a.valid.end is None:
                    continue  # no temporal claim to violate

                for role, other_id in (("subject", a.subject_id), ("target", a.object_id)):
                    span = self._existence_window(other_id, as_of=as_of)
                    if span is None:
                        continue
                    start, end = span
                    if end is not None and a.valid.start is not None and a.valid.start >= end:
                        out.append(InvalidRelationship(
                            a, f"the {role} no longer existed after {end}",
                            subject=self.graph.get_entity(a.subject_id),
                            target=self.graph.get_entity(a.object_id)))
                    elif start is not None and a.valid.end is not None and a.valid.end <= start:
                        out.append(InvalidRelationship(
                            a, f"the {role} did not exist until {start}",
                            subject=self.graph.get_entity(a.subject_id),
                            target=self.graph.get_entity(a.object_id)))
        return out

    def _existence_window(self, entity_id, as_of=None):
        """The window an entity existed for, from any bounded `alive`/existence
        assertion. `None` when nothing says."""
        for a in self.graph.history_of(entity_id):
            if a.is_retracted or a.predicate not in ("alive", "exists", "active"):
                continue
            if a.valid.start is None and a.valid.end is None:
                continue
            return a.valid.start, a.valid.end
        return None

    # -- mitigating evidence -----------------------------------------------

    def mitigated(self, space_id, contradiction, as_of=None):
        """Is there anything in the graph that *explains* this conflict?

        Adapted from the sharpest idea in Story Atlas's canon engine: two
        opposing facts about the same pair are only worth flagging if nothing
        recorded could account for the change. A character who is both an ally
        and an enemy is a plot, not a bug — provided something happened in
        between.

        Generalised here: a contradiction is **mitigated** when a third fact
        about the same subject sits between the two disputed windows. That
        intervening fact is the bridge, and reporting it alongside the conflict
        turns "these disagree" into "these disagree, and this may be why" —
        which is the difference between a checker a writer trusts and one they
        switch off.

        Returns the bridging assertions, or `[]` when nothing explains it.
        """
        left, right = contradiction.left, contradiction.right
        window_start = min(w for w in (left.valid.start, right.valid.start)
                           if w is not None) if (left.valid.start is not None
                                                 or right.valid.start is not None) else None
        window_end = max(w for w in (left.valid.end, right.valid.end)
                         if w is not None) if (left.valid.end is not None
                                               or right.valid.end is not None) else None

        bridges = []
        for a in self.graph.history_of(contradiction.subject_id):
            if a.is_retracted or a.id in (left.id, right.id):
                continue
            if a.predicate == contradiction.predicate:
                continue   # another value of the same thing is more conflict, not a bridge
            if a.valid.start is None and a.valid.end is None:
                continue   # timeless facts explain nothing about a change
            point = a.valid.start if a.valid.start is not None else a.valid.end
            if window_start is not None and point < window_start:
                continue
            if window_end is not None and point > window_end:
                continue
            bridges.append(a)
        return bridges

    def explained_contradictions(self, space_id, entity_id=None, as_of=None):
        """Contradictions paired with whatever might account for them.

        `[(contradiction, [bridging assertions]), ...]`. An empty bridge list
        means nothing in the graph explains it — those are the ones worth a
        writer's attention first.
        """
        found = self.graph.contradictions(space_id, entity_id=entity_id, as_of=as_of)
        return [(c, self.mitigated(space_id, c, as_of=as_of)) for c in found]

    def unexplained_contradictions(self, space_id, entity_id=None, as_of=None):
        return [c for c, bridges in
                self.explained_contradictions(space_id, entity_id, as_of) if not bridges]

    # -- the whole verdict -------------------------------------------------

    def verify_entity(self, entity_id, as_of=None, threshold=0.5):
        entity = self.graph.get_entity(entity_id)
        if entity is None:
            return Verdict()
        return Verdict(
            evidence=self.evidence_for(entity_id, as_of=as_of),
            contradictions=self.graph.contradictions(
                entity.space_id, entity_id=entity_id, as_of=as_of),
            unsupported=self.unsupported_claims(entity_id, threshold=threshold),
        )

    def verify_space(self, space_id, as_of=None):
        return Verdict(
            contradictions=self.graph.contradictions(space_id, as_of=as_of),
            ambiguities=self.ambiguities(space_id),
            invalid_relationships=self.invalid_relationships(space_id, as_of=as_of),
        )
