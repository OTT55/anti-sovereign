"""Answering a plain question by *traversing the graph*, never by guessing.

Lifted from the best idea in `companies/creativeos/story-atlas/app.py`: a small
intent parser maps a natural question onto a real traversal, and **every answer
explains the method that produced it**. That `explain` field is what separates
this from a chatbot — a reader can check the reasoning rather than trust it.

Three ideas from that app were worth generalising, and all three are here:

* **Intent → traversal.** A fixed vocabulary of questions, each mapped to a
  query the graph can actually answer. No model, no embedding, no guessing at
  what was meant — and when nothing matches, it says so and lists what it *can*
  answer instead of inventing a response.
* **Negative queries.** "Who has never met X" is the question that revealed
  the gap: every engine could find connections and none could find their
  *absence*. Absence is often the more useful answer — an unused character, an
  asset nobody licensed, a creator nobody hired.
* **Consequences, not just connections.** "What happens if X is removed" should
  say *what must change*, not merely list neighbours.

Domain-neutral, per Constitution v2.0: it knows entities and relationships, not
characters and scenes. StoryAtlas supplies the vocabulary that makes the answers
read like narrative questions.
"""

import re

#: Question shapes, most specific first — "who has never met X" must be tested
#: before "who is connected to X", or the negative case is swallowed by the
#: positive one.
INTENTS = [
    ("never-connected", (
        r"\bnever\b.*\b(met|meet|encountered|interacted|connected|worked)\b",
        r"\bwho\b.*\b(hasn'?t|has not|have not|haven'?t)\b",
        r"\bnot connected\b", r"\bno connection\b", r"\bunconnected\b",
    )),
    ("impact", (
        r"\bwhat (happens|changes) if\b", r"\bimpact of\b", r"\bif .* (dies|died|leaves|is removed)\b",
        r"\bremove\b", r"\bwithout\b.*\bwhat\b", r"\bconsequences?\b",
    )),
    ("path", (
        r"\bhow (is|are) .* (connected|related|linked)\b",
        r"\bconnection between\b", r"\brelationship between\b",
        r"\bpath (from|between)\b", r"\blink between\b",
    )),
    ("timeline", (
        r"\bwhen\b", r"\bwhat year\b", r"\btimeline\b", r"\bin \d{3,4}\b",
        r"\bbefore\b.*\bafter\b", r"\bchronolog",
    )),
    ("conflicts", (
        r"\bcontradict", r"\bconflict", r"\binconsistenc", r"\bwrong\b",
        r"\bproblems?\b", r"\berrors?\b", r"\bwhat needs (fixing|attention)\b",
    )),
    ("missing", (
        r"\bmissing\b", r"\bincomplete\b", r"\bgaps?\b", r"\bwhat (don'?t|do not) we know\b",
        r"\bnot recorded\b", r"\bunknown\b",
    )),
    ("important", (
        r"\bmost important\b", r"\bwho matters\b", r"\bwhat matters\b",
        r"\bcentral\b", r"\bkey (characters?|entities|people)\b", r"\bmain\b",
    )),
    ("connections", (
        r"\bconnected to\b", r"\brelated to\b", r"\bwho knows\b",
        r"\blinked to\b", r"\bassociated with\b", r"\bconnections? of\b",
    )),
    ("profile", (
        r"\bwho is\b", r"\bwhat is\b", r"\btell me about\b", r"\bdescribe\b",
        r"\bprofile of\b", r"\beverything about\b",
    )),
]

_COMPILED = [(name, [re.compile(p, re.IGNORECASE) for p in patterns])
             for name, patterns in INTENTS]

#: Words that are never part of an entity name in a question.
_NOISE = {
    "who", "what", "when", "where", "why", "how", "is", "are", "was", "were",
    "the", "a", "an", "of", "to", "in", "on", "at", "for", "with", "and", "or",
    "me", "my", "we", "our", "tell", "about", "show", "list", "find", "give",
    "does", "did", "do", "has", "have", "had", "been", "being", "be", "if",
    "happens", "changes", "change", "impact", "never", "met", "meet", "not",
    "connected", "connection", "connections", "between", "path", "from",
    "removed", "remove", "dies", "died", "leaves", "important", "matters",
    "most", "main", "key", "central", "everything", "describe", "profile",
    "conflicts", "conflict", "missing", "gaps", "gap", "timeline", "year",
    "related", "linked", "knows", "consequences", "consequence", "that",
}


class Answer:
    """One answer, with the traversal that produced it made visible."""

    __slots__ = ("intent", "headline", "items", "explain", "subject", "question")

    def __init__(self, intent, headline, items=None, explain="", subject=None, question=""):
        self.intent = intent
        self.headline = headline
        self.items = items or []
        self.explain = explain
        self.subject = subject
        self.question = question

    def describe(self):
        return f"[{self.intent}] {self.headline}"

    def render(self):
        lines = [self.headline, ""]
        for item in self.items:
            note = f" — {item['note']}" if item.get("note") else ""
            lines.append(f"- {item['name']}{note}")
        if self.explain:
            lines += ["", f"How: {self.explain}"]
        return "\n".join(lines).strip()

    def __repr__(self):
        return f"<Answer {self.describe()}>"


class Assistant:
    """Natural questions, answered by traversal.

    Built on the Intelligence Engine so it inherits Search, Reasoning and
    Verification rather than reimplementing any of them.
    """

    def __init__(self, intelligence):
        self.brain = intelligence
        self.graph = intelligence.graph

    # -- parsing -----------------------------------------------------------

    def classify(self, question):
        for name, patterns in _COMPILED:
            if any(p.search(question) for p in patterns):
                return name
        return "unknown"

    def find_entity(self, space_id, question, exclude=()):
        """The entity a question is about.

        Tries the graph's own names against the question rather than parsing
        the question into names — far more robust, because the graph already
        knows every name that exists and a question rarely contains anything
        else worth matching.
        """
        candidates = []
        lowered = question.lower()
        for entity in self.graph.find_entities(space_id):
            if entity.id in exclude or entity.name in exclude:
                continue
            name = entity.name.lower()
            if name in lowered:
                candidates.append((len(name), entity))
                continue
            # A distinctive word from the name — "Vane" for "Chancellor Aldric Vane".
            for token in name.split():
                if len(token) > 3 and token not in _NOISE and re.search(
                        rf"\b{re.escape(token)}\b", lowered):
                    candidates.append((len(token), entity))
                    break
        if not candidates:
            return None
        candidates.sort(key=lambda pair: -pair[0])
        return candidates[0][1]

    def find_two(self, space_id, question):
        first = self.find_entity(space_id, question)
        if first is None:
            return None, None
        second = self.find_entity(space_id, question, exclude=(first.id,))
        return first, second

    # -- answering ---------------------------------------------------------

    def ask(self, space_id, question):
        intent = self.classify(question)
        handler = getattr(self, f"_answer_{intent.replace('-', '_')}", None)
        if handler is None:
            return self._unknown(question)
        answer = handler(space_id, question)
        answer.question = question
        return answer

    def _unknown(self, question):
        return Answer(
            "unknown",
            "I can only answer by traversing the graph, and nothing in that question matched.",
            items=[{"name": name} for name in (
                "who is X", "who is connected to X", "who has never met X",
                "how are X and Y connected", "what happens if X is removed",
                "what contradicts", "what is missing", "what matters most",
            )],
            explain="Rather than guess at an answer, this lists the question shapes "
                    "that map onto a real traversal.",
            question=question,
        )

    def _needs_subject(self, question):
        return Answer(
            "unknown", "I could not find anything in this space matching that question.",
            explain="Every answer is a traversal from a known entity, so the question "
                    "has to name one.",
            question=question,
        )

    # -- the traversals ----------------------------------------------------

    def _answer_profile(self, space_id, question):
        entity = self.find_entity(space_id, question)
        if entity is None:
            return self._needs_subject(question)
        context = self.graph.context_of(entity.id)
        items = [{"name": f"{k}: {v}", "note": "recorded fact"}
                 for k, v in sorted(context["state"].items())]
        items += [{"name": other.name, "note": assertion.predicate}
                  for assertion, other in context["relationships"]]
        return Answer(
            "profile", f"{entity.name} — {len(items)} recorded detail(s)", items,
            explain="Everything the graph holds about this entity: its current "
                    "state, its relationships, and any conflicts.",
            subject={"id": entity.id, "name": entity.name},
        )

    def _answer_connections(self, space_id, question):
        entity = self.find_entity(space_id, question)
        if entity is None:
            return self._needs_subject(question)
        hits = self.brain.search.traverse(space_id, entity.id, depth=2)
        return Answer(
            "connections", f"{entity.name} is connected to {len(hits)} entity(ies)",
            [{"name": h.entity.name, "note": f"{h.via} ({len(h.path) - 1} hop(s))"}
             for h in hits],
            explain="A breadth-first walk out to two hops. Nearer connections rank "
                    "higher, and each carries the path that reached it.",
            subject={"id": entity.id, "name": entity.name},
        )

    def _answer_never_connected(self, space_id, question):
        """The question that revealed the gap: every engine could find
        connections and none could find their absence."""
        entity = self.find_entity(space_id, question)
        if entity is None:
            return self._needs_subject(question)

        reachable = {h.entity.id for h in
                     self.brain.search.traverse(space_id, entity.id, depth=2)}
        reachable.add(entity.id)
        isolated = [e for e in self.graph.find_entities(space_id)
                    if e.id not in reachable]
        return Answer(
            "never-connected",
            f"{len(isolated)} entity(ies) have no connection to {entity.name}",
            [{"name": e.name, "note": e.kind} for e in isolated],
            explain="Everything within two hops is subtracted from everything that "
                    "exists. What remains shares no path with the subject — often "
                    "the more useful answer, since it finds what is unused.",
            subject={"id": entity.id, "name": entity.name},
        )

    def _answer_path(self, space_id, question):
        first, second = self.find_two(space_id, question)
        if first is None or second is None:
            return self._needs_subject(question)
        paths = self.brain.reasoning.paths_between(first.id, second.id)
        if not paths:
            return Answer(
                "path", f"{first.name} and {second.name} are not connected.",
                explain="A breadth-first search to four hops found no route between them.",
                subject={"id": first.id, "name": first.name})
        return Answer(
            "path", f"{first.name} reaches {second.name} in {paths[0].length} step(s)",
            [{"name": p.describe(), "note": f"{p.length} hop(s)"} for p in paths],
            explain="Every route between the two, shortest first. The route is the "
                    "explanation — a long one is usually coincidence rather than meaning.",
            subject={"id": first.id, "name": first.name},
        )

    def _answer_impact(self, space_id, question):
        """Consequences, not just connections — what must *change*."""
        entity = self.find_entity(space_id, question)
        if entity is None:
            return self._needs_subject(question)
        impact = self.brain.reasoning.impact_of_removing(entity.id)
        if impact is None:
            return self._needs_subject(question)

        items = []
        for other in impact.orphaned:
            items.append({"name": other.name,
                          "note": "would be left with no connections at all"})
        for other in impact.direct:
            if other not in impact.orphaned:
                items.append({"name": other.name, "note": "loses a direct connection"})
        for other in impact.indirect:
            items.append({"name": other.name, "note": "connected indirectly — may be affected"})
        if impact.implications_lost:
            items.append({"name": f"{len(impact.implications_lost)} implied fact(s)",
                          "note": "no longer follow from the graph"})

        return Answer(
            "impact", f"Removing {entity.name} touches {len(items)} element(s)",
            items,
            explain="Direct connections, what they would be left with, and the implied "
                    "facts that stop following. Anything left with no connections at "
                    "all counts double — losing one edge is inconvenient, losing your "
                    "last one is disappearing.",
            subject={"id": entity.id, "name": entity.name},
        )

    def _answer_conflicts(self, space_id, question):
        verdict = self.brain.verification.verify_space(space_id)
        problems = (verdict.contradictions + verdict.invalid_relationships
                    + verdict.ambiguities)
        return Answer(
            "conflicts", f"{len(problems)} problem(s) found",
            [{"name": p.describe()} for p in problems],
            explain="Deterministic checks: facts that disagree over overlapping time, "
                    "relationships their own endpoints do not support, and names "
                    "meaning more than one thing. No judgement, no guessing.",
        )

    def _answer_missing(self, space_id, question):
        gaps = self.brain.what_is_missing(space_id)
        return Answer(
            "missing", f"{len(gaps)} gap(s) found",
            [{"name": g.entity.name, "note": f"no {g.missing} — {g.reason}"} for g in gaps],
            explain="Not everything absent — only what comparable entities have. If "
                    "nobody records a thing, its absence is not a gap.",
        )

    def _answer_important(self, space_id, question):
        ranked = self.brain.what_matters(space_id)
        return Answer(
            "important", f"{len(ranked)} entity(ies) ranked by importance",
            [{"name": name, "note": f"score {score}"} for name, score in ranked],
            explain="Importance is not stored anywhere — it is computed from how "
                    "connected a thing is, how much is known about it, and how much "
                    "would break without it.",
        )

    def _answer_timeline(self, space_id, question):
        year = re.search(r"\b(\d{3,5})\b", question)
        if year:
            point = int(year.group(1))
            hits = self.brain.search.during(space_id, start=point, end=point + 1)
            return Answer(
                "timeline", f"{len(hits)} entity(ies) had a fact true in {point}",
                [{"name": h.entity.name, "note": h.via} for h in hits],
                explain="Entities carrying a dated fact whose valid-time window covers "
                        "that year. Undated facts make no claim about when, so they "
                        "are not counted.")

        entity = self.find_entity(space_id, question)
        if entity is None:
            return self._needs_subject(question)
        dated = [a for a in self.graph.history_of(entity.id)
                 if not a.is_retracted and (a.valid.start or a.valid.end)]
        return Answer(
            "timeline", f"{entity.name} has {len(dated)} dated fact(s)",
            [{"name": f"{a.predicate}: {a.object_repr()}", "note": a.valid.describe()}
             for a in dated],
            explain="Every fact about this entity that carries a valid-time window, "
                    "in the order it was recorded.",
            subject={"id": entity.id, "name": entity.name},
        )
