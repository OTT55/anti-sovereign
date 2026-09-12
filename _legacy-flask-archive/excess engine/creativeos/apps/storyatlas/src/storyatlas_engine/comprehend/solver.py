"""Solving for the dates the draft never states.

This is the mathematics, and it is the reason the engine can do something a
keyword matcher cannot. A writer states a handful of dates and relates
everything else to them. Treat each relation as an equation and the unstated
dates stop being unknown:

    Aldric was born in 1102.              ->  birth(Aldric)  = 1102
    He was crowned at the age of thirty.  ->  accession      = birth + 30 = 1132
    Three years later, the war began.     ->  battle         = 1132 + 3  = 1135
    Mara died that same year.             ->  death(Mara)    = 1135

Four events, one stated date. Everything else is arithmetic over a dependency
graph, resolved by propagating to a fixpoint — no model, no guessing, and the
same input always gives the same answer.

Two properties matter as much as the arithmetic:

* **It reports what it could not solve** rather than filling in a plausible
  number. An unresolved event keeps `year = None` and still gets an `order`, so
  it can be placed in sequence without being given a date it does not have.
* **It detects when the equations disagree.** If a stated year contradicts a
  computed one, that is a continuity error in the draft, and saying so is the
  product.
"""

from .temporal import TimeRef


class Placement:
    """Where one event sits in time once the constraints are solved."""

    __slots__ = ("event", "year", "source", "order", "conflict")

    def __init__(self, event, year=None, source="unknown", order=0, conflict=None):
        self.event = event
        self.year = year
        self.source = source      # "stated" | "computed" | "unknown"
        self.order = order
        self.conflict = conflict

    @property
    def is_dated(self):
        return self.year is not None

    def describe(self):
        when = f"{self.year} ({self.source})" if self.is_dated else "undated"
        return f"{self.event.kind}: {self.event.subject or '?'} — {when}"

    def __repr__(self):
        return f"<Placement {self.describe()}>"


class Timeline:
    """The solved chronology: placements, conflicts, and what stayed unknown."""

    def __init__(self, placements, conflicts):
        self.placements = placements
        self.conflicts = conflicts

    @property
    def dated(self):
        return [p for p in self.placements if p.is_dated]

    @property
    def undated(self):
        return [p for p in self.placements if not p.is_dated]

    def in_order(self):
        """Every event in chronological order.

        Dated events sort by year. Undated ones keep the position the narrative
        gave them, which is information too — a draft's own ordering is usually
        right even when its dates are absent.
        """
        return sorted(self.placements, key=lambda p: (p.year if p.is_dated else _between(p, self.placements), p.order))

    def by_kind(self, kind):
        return [p for p in self.placements if p.event.kind == kind]

    def for_subject(self, name):
        return [p for p in self.placements if p.event.subject == name]


def _between(placement, placements):
    """Give an undated event a sort key from its dated neighbours, so it lands
    between them rather than at the start of the timeline."""
    before = [p.year for p in placements
              if p.is_dated and p.order < placement.order]
    return max(before) if before else float("-inf")


def solve(events, birth_years=None):
    """Resolve every event's date from the constraints, and report conflicts.

    `birth_years` optionally seeds known birth dates so "at the age of thirty"
    can be computed for characters whose birth is recorded elsewhere.
    """
    placements = [Placement(e, order=i) for i, e in enumerate(events)]
    conflicts = []

    # Pass 1 — stated dates. These are the anchors everything else hangs off.
    for p in placements:
        t = p.event.time
        if t is not None and t.kind == "absolute":
            p.year = t.value
            p.source = "stated"

    # Pass 2 — births, so ages become computable.
    births = dict(birth_years or {})
    for p in placements:
        if p.event.kind == "birth" and p.is_dated and p.event.subject:
            births.setdefault(p.event.subject, p.year)

    # Pass 3 — propagate offsets, "same", and ages until nothing more resolves.
    # A fixpoint loop rather than a single sweep, because an offset may depend on
    # an anchor that is itself only resolved later in the chain. Bounded by the
    # number of events, since each iteration resolves at least one or stops.
    for _ in range(len(placements) + 1):
        progressed = False
        for i, p in enumerate(placements):
            if p.is_dated:
                continue
            t = p.event.time
            if t is None:
                continue

            if t.kind == "age":
                birth = births.get(p.event.subject)
                if birth is not None:
                    p.year, p.source, progressed = birth + t.value, "computed", True
                continue

            if t.kind in ("offset", "same"):
                anchor = _nearest_anchor(placements, i)
                if anchor is not None:
                    delta = t.value if t.kind == "offset" else 0
                    p.year, p.source, progressed = anchor + delta, "computed", True
                continue

        # Newly dated births feed the next round of age calculations.
        for p in placements:
            if p.event.kind == "birth" and p.is_dated and p.event.subject:
                if p.event.subject not in births:
                    births[p.event.subject] = p.year
                    progressed = True

        if not progressed:
            break

    # Pass 4 — check the equations agree with each other.
    for i, p in enumerate(placements):
        t = p.event.time
        if t is None or not p.is_dated:
            continue
        anchor = _nearest_anchor(placements, i)
        if anchor is None:
            continue
        if t.kind == "offset" and t.value > 0 and p.year <= anchor:
            conflicts.append(_conflict(p, anchor, "says it happened later, but resolves to the same year or earlier"))
        elif t.kind == "offset" and t.value < 0 and p.year >= anchor:
            conflicts.append(_conflict(p, anchor, "says it happened earlier, but resolves to the same year or later"))
        elif t.kind == "after" and p.source == "stated" and p.year < anchor:
            conflicts.append(_conflict(p, anchor, "follows the previous event in the text but is dated before it"))
        elif t.kind == "before" and p.source == "stated" and p.year > anchor:
            conflicts.append(_conflict(p, anchor, "precedes the previous event in the text but is dated after it"))

        # A clause stating both a date and a relation must agree with itself.
        if t.secondary is not None and t.kind == "absolute":
            expected = anchor + (t.secondary.value or 0)
            if expected != p.year:
                conflicts.append(_conflict(
                    p, anchor,
                    f"says \"{t.secondary.text}\", which works out to {expected}, "
                    f"but states the year {p.year}",
                ))

    return Timeline(placements, conflicts)


def _nearest_anchor(placements, index):
    """The closest already-dated event before this one; failing that, after it.

    Looking backwards first matches how prose works — "three years later" means
    later than what was just described. Falling forward covers a flashback whose
    only date arrives afterwards.
    """
    for j in range(index - 1, -1, -1):
        if placements[j].is_dated:
            return placements[j].year
    for j in range(index + 1, len(placements)):
        if placements[j].is_dated:
            return placements[j].year
    return None


def _conflict(placement, anchor, problem):
    return {
        "event": placement.event,
        "year": placement.year,
        "anchor": anchor,
        "problem": problem,
        "text": placement.event.text,
    }


def lifespans(timeline):
    """Birth and death per character, as `{name: (born, died)}`.

    This is what makes a character's dates checkable at all: once someone has a
    lifespan, any event naming them outside it is a continuity error — and it is
    the shape CreativeOS's `ValidWindow` wants, so the graph can then verify it.
    """
    spans = {}
    for p in timeline.placements:
        subject = p.event.subject
        if not subject or not p.is_dated:
            continue
        born, died = spans.get(subject, (None, None))
        if p.event.kind == "birth" and born is None:
            born = p.year
        elif p.event.kind == "death" and died is None:
            died = p.year
        spans[subject] = (born, died)
    return spans
