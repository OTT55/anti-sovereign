"""The Intelligence Engine — *"This is the brain of CreativeOS."*

Constitution v2.0: *"Coordinates every engine. Produces ecosystem intelligence.
Answers: What exists? What changed? What is connected? What matters? What is
missing? What happens next?"*

Six questions, six methods, each delegating to the engine that owns the
capability rather than reimplementing it. That is the whole job: this engine
contains almost no logic of its own, and that is correct — a coordinator that
starts computing things is a coordinator that has quietly become a second
implementation.

The one genuinely new idea here is **what matters**. Nothing else ranks
importance, and it cannot be retrieved because it is not a property of any
record: an entity matters in proportion to how connected it is, how much is
known about it, how recently it changed, and how much would break without it.
That is a judgement, but a computable one.
"""

from ..context import ContextEngine
from ..reasoning import ReasoningEngine
from ..search import SearchEngine
from ..verification import VerificationEngine


class Briefing:
    """Everything the Intelligence Engine has to say about a space."""

    def __init__(self, space_id, exists, changed, matters, missing,
                 next_up, verdict):
        self.space_id = space_id
        self.exists = exists
        self.changed = changed
        self.matters = matters
        self.missing = missing
        self.next_up = next_up
        self.verdict = verdict

    def summary(self):
        return {
            "entities": self.exists["total"],
            "recent_changes": len(self.changed),
            "key_entities": [name for name, _ in self.matters[:5]],
            "gaps": len(self.missing),
            "recommendations": len(self.next_up),
            "contradictions": len(self.verdict.contradictions),
            "certainty_issues": len(self.verdict.invalid_relationships)
                                + len(self.verdict.ambiguities),
        }

    def render(self):
        lines = [f"# Space briefing", ""]
        lines.append(f"{self.exists['total']} entities: " + ", ".join(
            f"{n} {k}" for k, n in sorted(self.exists["by_kind"].items())))
        lines.append("")

        if self.matters:
            lines.append("## What matters")
            for name, score in self.matters[:5]:
                lines.append(f"- {name} ({score:.2f})")
            lines.append("")

        if self.changed:
            lines.append("## What changed")
            for event in self.changed[:5]:
                lines.append(f"- {event.describe()}")
            lines.append("")

        problems = (self.verdict.contradictions + self.verdict.ambiguities
                    + self.verdict.invalid_relationships)
        if problems:
            lines.append("## What needs attention")
            for p in problems[:5]:
                lines.append(f"- {p.describe()}")
            lines.append("")

        if self.next_up:
            lines.append("## What to do next")
            for rec in self.next_up[:5]:
                lines.append(f"- {rec}")
        return "\n".join(lines).strip()


class IntelligenceEngine:
    def __init__(self, graph, search=None, context=None, reasoning=None,
                 verification=None):
        self.graph = graph
        self.search = search or SearchEngine(graph)
        self.context = context or ContextEngine(graph, self.search)
        self.reasoning = reasoning or ReasoningEngine(graph)
        self.verification = verification or VerificationEngine(graph)
        self._assistant = None

    @property
    def assistant(self):
        """Natural questions answered by traversal — see `assistant.py`."""
        if self._assistant is None:
            from .assistant import Assistant
            self._assistant = Assistant(self)
        return self._assistant

    def ask(self, space_id, question):
        """Answer a plain question about a space, showing its working."""
        return self.assistant.ask(space_id, question)

    # -- the six questions -------------------------------------------------

    def what_exists(self, space_id):
        entities = self.graph.find_entities(space_id)
        by_kind = {}
        for entity in entities:
            by_kind[entity.kind] = by_kind.get(entity.kind, 0) + 1
        return {"total": len(entities), "by_kind": by_kind,
                "names": sorted(e.name for e in entities)}

    def what_changed(self, space_id, since=0, limit=20):
        """Straight from the event log — the Memory Engine's promise in use."""
        return self.graph.bus.history(space_id=space_id, since=since)[-limit:]

    def what_is_connected(self, entity_id, depth=2):
        space = self.graph.get_entity(entity_id)
        if space is None:
            return []
        return self.search.traverse(space.space_id, entity_id, depth=depth)

    def what_matters(self, space_id, limit=10, at=None, as_of=None):
        """Rank entities by importance.

        Four signals, added rather than multiplied — unlike the Context Engine,
        where a zero should veto. Here a thing can matter for one strong reason
        alone: an entity with a single connection but a hundred recorded facts
        is still significant, and a product of signals would erase it.

          connections — how embedded it is in the graph
          knowledge   — how much has been recorded about it
          impact      — how much would break without it
          recency     — whether it is still being touched
        """
        entities = self.graph.find_entities(space_id)
        if not entities:
            return []

        # Computed once and shared across every impact below. Recomputing it
        # per entity is what made this quadratic.
        implications = self.reasoning.implications(space_id, at=at, as_of=as_of)

        raw = {}
        for entity in entities:
            neighbours = self.graph.neighbors(entity.id, at=at, as_of=as_of)
            history = [a for a in self.graph.history_of(entity.id) if not a.is_retracted]
            # Facts pointing *at* an entity are knowledge about it too. Counting
            # only assertions where it is the subject would rank an entity by the
            # accident of which way round its relationships happened to be
            # written, which is not a measure of anything.
            inbound = [a for a in self.graph.relationships_of(
                entity.id, at=at, as_of=as_of, direction="in")]
            impact = self.reasoning.impact_of_removing(
                entity.id, at=at, as_of=as_of, implications=implications)
            raw[entity.name] = {
                "connections": len(neighbours),
                "knowledge": len(history) + len(inbound),
                "impact": impact.severity if impact else 0,
            }

        def normalise(key):
            top = max((v[key] for v in raw.values()), default=0) or 1
            return {name: v[key] / top for name, v in raw.items()}

        connections = normalise("connections")
        knowledge = normalise("knowledge")
        impact = normalise("impact")

        scored = [
            (name,
             round(connections[name] * 0.35 + knowledge[name] * 0.3 + impact[name] * 0.35, 4))
            for name in raw
        ]
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        return scored[:limit]

    def what_is_missing(self, space_id, limit=20):
        return self.reasoning.gaps(space_id)[:limit]

    def what_happens_next(self, space_id, limit=10):
        """Recommendations, ordered by how much they would improve the graph.

        Contradictions first: an unresolved conflict makes every answer drawn
        from those facts unreliable, so it outranks anything merely absent.
        """
        recommendations = []
        verdict = self.verification.verify_space(space_id)

        for c in verdict.contradictions:
            recommendations.append(f"Resolve the conflict — {c.describe()}")
        for r in verdict.invalid_relationships:
            recommendations.append(f"Check this relationship — {r.describe()}")
        for a in verdict.ambiguities:
            recommendations.append(f"Disambiguate — {a.describe()}")
        for gap in self.reasoning.gaps(space_id)[:5]:
            recommendations.append(f"Fill the gap — {gap.describe()}")

        implied = self.reasoning.implications(space_id)
        for i in implied[:3]:
            recommendations.append(f"Confirm the implication — {i.describe()}")

        return recommendations[:limit]

    # -- everything at once ------------------------------------------------

    def brief(self, space_id, since=0):
        return Briefing(
            space_id=space_id,
            exists=self.what_exists(space_id),
            changed=self.what_changed(space_id, since=since),
            matters=self.what_matters(space_id),
            missing=self.what_is_missing(space_id),
            next_up=self.what_happens_next(space_id),
            verdict=self.verification.verify_space(space_id),
        )
