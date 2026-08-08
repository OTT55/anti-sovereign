"""The Context Engine — assembling what matters, and *budgeting* it.

Constitution v2.0: *"Builds contextual understanding. Assembles relevant
information across every application. **Injects only necessary knowledge** into
AI reasoning. Acts as the ecosystem's context layer."*

The second sentence is the hard one. Retrieval finds everything relevant;
context has to decide what is worth the space. A context window is finite, so
this is a knapsack problem — maximise usefulness under a size limit — and the
interesting design question is what "usefulness" means.

Three signals, multiplied:

* **relevance** — how well it matched the question (from Search)
* **confidence** — how sure the graph is of the fact (from the assertion)
* **recency** — how recently it was asserted

Multiplied rather than added, deliberately: a fact nobody is confident in should
not buy its way into the context by being extremely relevant. Any signal near
zero should veto, which addition does not do.

Contradictions are exempt from the budget and always included. A context that
omits the fact that its own contents disagree is worse than no context — it
produces confident answers built on a conflict nobody was told about.
"""

from ..search import SearchEngine


class Fragment:
    """One piece of context, with the score that earned it a place."""

    __slots__ = ("kind", "text", "entity_id", "entity_name", "score",
                 "source", "size", "detail")

    def __init__(self, kind, text, entity_id=None, entity_name=None, score=0.0,
                 source="", detail=None):
        self.kind = kind          # "entity" | "fact" | "relationship" | "contradiction"
        self.text = text
        self.entity_id = entity_id
        self.entity_name = entity_name
        self.score = score
        self.source = source      # provenance of the underlying assertion
        self.size = len(text)
        self.detail = detail or {}

    def describe(self):
        return f"[{self.kind}] {self.text}"

    def __repr__(self):
        return f"<Fragment {self.kind} {self.score:.3f}>"


class Context:
    """Assembled context, plus an honest account of what was left out.

    The budget governs the **fragments selected**, not the length of `render()`.
    Rendering adds entity headings and an omission notice, so on a very small
    budget the notice can cost more than the fragment it replaced. Callers
    needing a hard cap on the rendered string should measure `render()` directly.
    """

    def __init__(self, question, fragments, dropped, budget, space_id):
        self.question = question
        self.fragments = fragments
        self.dropped = dropped
        self.budget = budget
        self.space_id = space_id

    @property
    def size(self):
        return sum(f.size for f in self.fragments)

    @property
    def entities(self):
        return sorted({f.entity_name for f in self.fragments if f.entity_name})

    def contradictions(self):
        return [f for f in self.fragments if f.kind == "contradiction"]

    def render(self):
        """Plain text, grouped by entity — the shape a prompt or a report wants."""
        lines = []
        if self.question:
            lines.append(f"Question: {self.question}")
            lines.append("")
        by_entity = {}
        for f in self.fragments:
            by_entity.setdefault(f.entity_name or "(general)", []).append(f)
        for name, group in by_entity.items():
            lines.append(f"## {name}")
            for f in group:
                lines.append(f"- {f.text}")
            lines.append("")
        if self.dropped:
            lines.append(f"({len(self.dropped)} lower-ranked items omitted for space)")
        return "\n".join(lines).strip()

    def summary(self):
        return {
            "fragments": len(self.fragments),
            "dropped": len(self.dropped),
            "size": self.size,
            "budget": self.budget,
            "entities": len(self.entities),
            "contradictions": len(self.contradictions()),
        }


class ContextEngine:
    def __init__(self, graph, search=None):
        self.graph = graph
        self.search = search or SearchEngine(graph)

    def assemble(self, space_id, question=None, near=None, budget=2000,
                 depth=1, at=None, as_of=None, limit=12):
        """Gather context for a question, then fit it to `budget` characters.

        `near` anchors on a known entity; `question` is free text. Either alone
        works, both together is stronger.
        """
        seeds = self.search.find(space_id, query=question, near=near,
                                 depth=depth, limit=limit, at=at, as_of=as_of,
                                 rebuild=True)

        fragments = []
        seen = set()

        # The anchor itself belongs in its own context. Traversal deliberately
        # returns what is reachable *from* an entity, not the entity, so context
        # about Aldric would otherwise contain everyone except Aldric.
        if near is not None:
            anchor = self.graph.get_entity(near)
            if anchor is not None:
                seen.add(anchor.id)
                fragments.extend(self._fragments_for(anchor, 1.0, at=at, as_of=as_of))

        for hit in seeds:
            if hit.entity.id in seen:
                continue
            seen.add(hit.entity.id)
            fragments.extend(self._fragments_for(hit.entity, hit.score, at=at, as_of=as_of))

        fragments.sort(key=lambda f: -f.score)
        kept, dropped, used = [], [], 0

        # Contradictions bypass the budget entirely — see the module docstring.
        for f in fragments:
            if f.kind == "contradiction":
                kept.append(f)
                used += f.size

        for f in fragments:
            if f.kind == "contradiction":
                continue
            if used + f.size <= budget:
                kept.append(f)
                used += f.size
            else:
                dropped.append(f)

        kept.sort(key=lambda f: (f.entity_name or "", -f.score))
        return Context(question, kept, dropped, budget, space_id)

    def _fragments_for(self, entity, relevance, at=None, as_of=None):
        """Turn one entity into scored context fragments."""
        out = [Fragment(
            kind="entity",
            text=f"{entity.name} is a {entity.kind}"
                 + (f" ({entity.subkind})" if entity.subkind else ""),
            entity_id=entity.id, entity_name=entity.name,
            score=relevance * 1.0, source="graph",
        )]

        history = self.graph.history_of(entity.id)
        newest = len(history) or 1
        for position, a in enumerate(history):
            if a.is_retracted:
                continue  # a withdrawn fact must never reach a prompt
            recency = 0.5 + 0.5 * ((position + 1) / newest)
            score = relevance * a.confidence * recency
            when = f" ({a.valid.describe()})" if (a.valid.start or a.valid.end) else ""
            if a.object_id:
                other = self.graph.get_entity(a.object_id)
                target = other.name if other else a.object_id
                out.append(Fragment(
                    kind="relationship",
                    text=f"{entity.name} {a.predicate} {target}{when}",
                    entity_id=entity.id, entity_name=entity.name,
                    score=score, source=a.source_kind,
                    detail={"predicate": a.predicate, "target": target},
                ))
            else:
                out.append(Fragment(
                    kind="fact",
                    text=f"{entity.name} {a.predicate}: {a.object_value}{when}",
                    entity_id=entity.id, entity_name=entity.name,
                    score=score, source=a.source_kind,
                    detail={"predicate": a.predicate, "value": a.object_value},
                ))

        for c in self.graph.contradictions(entity.space_id, entity_id=entity.id,
                                           as_of=as_of):
            out.append(Fragment(
                kind="contradiction",
                text=f"CONFLICT — {entity.name} {c.describe()}",
                entity_id=entity.id, entity_name=entity.name,
                score=float("inf"), source="verification",
            ))
        return out
