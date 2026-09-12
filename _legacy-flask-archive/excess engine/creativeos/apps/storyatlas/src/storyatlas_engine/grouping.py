"""Phase 8 — grouping the *people* inside the timeline, not just the events.

The report from using the engine was exact: *"he's grouping the timelines well,
but he does not group characters when they appear within the timeline."* That is
right. `Reading.by_period()` buckets **events** into eras and stops there. Ask
who was alive in the 1140s, who actually turned up, who was born into it and who
was already gone, and there was nothing to ask.

Three groupings, three different questions:

* **Eras** — a slice of time, and the cast inside it. Alive is computed from
  interval overlap; appearing is counted from the text. The interesting number
  is the difference between the two, because *alive but never appearing* is
  where drafts quietly lose people.
* **Circles** — who keeps turning up with whom. Connected components over
  shared scenes: no clustering algorithm, no threshold to tune beyond "how many
  scenes together counts", and the same input always gives the same grouping.
* **Generations** — characters banded by birth year, which is what makes a
  three-generation saga readable as three generations.

None of this is inference. Every grouping is a set operation over dates the
solver already computed, which is why it can be trusted and why it is instant.
"""

from collections import defaultdict

from .comprehend.typing import CHARACTER
from .presence import date_scenes, existences


class Era:
    """One slice of the timeline, and everyone in it."""

    __slots__ = ("start", "end", "label", "alive", "appears", "born", "died",
                 "places", "events")

    def __init__(self, start, end, label, alive=None, appears=None, born=None,
                 died=None, places=None, events=None):
        self.start = start
        self.end = end
        self.label = label
        #: Characters whose lifetime overlaps this era — computed, not counted.
        self.alive = alive or []
        #: Characters the text actually puts here.
        self.appears = appears or []
        self.born = born or []
        self.died = died or []
        self.places = places or []
        self.events = events or []

    @property
    def offstage(self):
        """Alive through this era and never once on the page.

        Not an error — most people in a story are elsewhere most of the time.
        It is the single most useful thing this module computes, because it is
        the question a writer cannot answer by re-reading: *who did I forget?*
        """
        return sorted(set(self.alive) - set(self.appears))

    def describe(self):
        parts = [f"{self.label}: {len(self.alive)} alive, {len(self.appears)} on the page"]
        if self.born:
            parts.append(f"born {', '.join(self.born)}")
        if self.died:
            parts.append(f"died {', '.join(self.died)}")
        return " · ".join(parts)

    def __repr__(self):
        return f"<Era {self.label}>"


class Circle:
    """A group of characters who share scenes — a cast cluster."""

    __slots__ = ("members", "scenes", "places")

    def __init__(self, members, scenes, places=None):
        self.members = members
        self.scenes = scenes
        self.places = places or []

    @property
    def size(self):
        return len(self.members)

    def describe(self):
        where = f" around {', '.join(self.places)}" if self.places else ""
        return (f"{', '.join(self.members)} — {len(self.scenes)} shared "
                f"scene{'' if len(self.scenes) == 1 else 's'}{where}")

    def __repr__(self):
        return f"<Circle {', '.join(self.members)}>"


def eras(reading, span=10, era_label="Year"):
    """Bucket the timeline into periods and populate each with its cast.

    `span` is the width in years. The buckets are aligned to multiples of `span`
    so that the same draft always produces the same eras regardless of where its
    first event happens — a timeline whose boundaries move when you add a
    sentence is one nobody can navigate twice.
    """
    lives = existences(reading)
    people = {n: e for n, e in lives.items() if e.kind == CHARACTER}
    scene_dates = {d.scene_index: d for d in date_scenes(reading)}

    years = [p.year for p in reading.timeline.dated]
    years += [e.begins for e in lives.values() if e.begins is not None]
    years += [e.ends for e in lives.values() if e.ends is not None]
    if not years:
        return []

    first = (min(years) // span) * span
    last = (max(years) // span) * span

    events_by_bucket = defaultdict(list)
    for placement in reading.timeline.dated:
        events_by_bucket[(placement.year // span) * span].append(placement)

    appears_by_bucket = defaultdict(set)
    places_by_bucket = defaultdict(set)
    for placement in reading.timeline.dated:
        bucket = (placement.year // span) * span
        for name in (placement.event.agent, placement.event.patient):
            if name and reading.kind_of(name) == CHARACTER:
                appears_by_bucket[bucket].add(name)
        if placement.event.place:
            places_by_bucket[bucket].add(placement.event.place)
    for scene in reading.scenes:
        date = scene_dates.get(scene.index)
        if date is None or date.year is None:
            continue
        bucket = (date.year // span) * span
        for name in scene.present:
            if reading.kind_of(name) == CHARACTER:
                appears_by_bucket[bucket].add(name)
        if scene.place:
            places_by_bucket[bucket].add(scene.place)

    out = []
    for start in range(first, last + span, span):
        end = start + span - 1
        alive = sorted(
            name for name, e in people.items()
            if _overlaps_window(e, start, end))
        out.append(Era(
            start=start, end=end, label=f"{era_label} {start}–{end}",
            alive=alive,
            appears=sorted(appears_by_bucket.get(start, ())),
            born=sorted(n for n, e in people.items()
                        if e.begins is not None and start <= e.begins <= end),
            died=sorted(n for n, e in people.items()
                        if e.ends is not None and start <= e.ends <= end),
            places=sorted(places_by_bucket.get(start, ())),
            events=events_by_bucket.get(start, []),
        ))
    return out


def _overlaps_window(existence, start, end):
    """Does an existence interval intersect `[start, end]`?

    An unbounded end means "still going as far as the draft says", which is the
    only reading that does not either kill everyone off at their last mention or
    keep them alive forever.
    """
    if existence.begins is None and existence.ends is None:
        return False
    if existence.begins is not None and existence.begins > end:
        return False
    if existence.ends is not None and existence.ends < start:
        return False
    return True


def cast_at(reading, year):
    """Who is alive in a given year — `[name, ...]`.

    The single-year form of an era, and the query a writer types when they are
    about to write a scene: *who can I put in this room?*
    """
    return sorted(name for name, e in existences(reading).items()
                  if e.kind == CHARACTER and e.contains(year) is True)


def co_presence(reading):
    """`{(a, b): [scene indices]}` for every pair sharing at least one scene.

    Pairs are ordered alphabetically so `(a, b)` and `(b, a)` are one key. That
    is not tidiness — an unordered pair counted twice doubles every edge weight
    in the mind map and silently changes which characters look central.
    """
    pairs = defaultdict(list)
    for scene in reading.scenes:
        people = sorted(n for n in scene.present if reading.kind_of(n) == CHARACTER)
        for i, first in enumerate(people):
            for second in people[i + 1:]:
                pairs[(first, second)].append(scene.index)
    return dict(pairs)


def circles(reading, minimum=1):
    """Group characters into clusters by shared scenes.

    Connected components, not statistical clustering: two characters are in the
    same circle if a chain of shared scenes links them. `minimum` is how many
    scenes a pair must share before the link counts — raise it and the loose
    fringe falls away, leaving only the groups that genuinely recur.

    Chosen over a similarity threshold because a component is *explainable*. A
    writer can be shown the exact chain of scenes that put two characters in one
    group, which they cannot be shown for a distance metric.
    """
    pairs = {pair: scenes for pair, scenes in co_presence(reading).items()
             if len(scenes) >= minimum}

    adjacency = defaultdict(set)
    for (first, second) in pairs:
        adjacency[first].add(second)
        adjacency[second].add(first)

    everyone = sorted(n for n, v in reading.types.items() if v.kind == CHARACTER)
    seen, out = set(), []

    for name in everyone:
        if name in seen:
            continue
        component, stack = [], [name]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            component.append(current)
            stack.extend(sorted(adjacency[current] - seen))
        component.sort()

        scenes = sorted({i for pair, indices in pairs.items()
                         if pair[0] in component for i in indices})
        places = sorted({s.place for s in reading.scenes
                         if s.index in scenes and s.place})
        out.append(Circle(component, scenes, places))

    return sorted(out, key=lambda c: (-c.size, c.members[0] if c.members else ""))


def generations(reading, span=25):
    """Characters banded by birth year — `[(band_start, [names]), ...]`.

    A generation is a *birth* cohort, not a slice of the timeline: people born
    within `span` years of each other. That is what makes a family saga legible
    as generations rather than as one long list of names.
    """
    banded = defaultdict(list)
    for name, existence in existences(reading).items():
        if existence.kind != CHARACTER or existence.begins is None:
            continue
        banded[(existence.begins // span) * span].append(name)
    return [(start, sorted(names)) for start, names in sorted(banded.items())]


def timeline_grid(reading, span=10, era_label="Year"):
    """A character-by-era grid, ready to print or render.

    `{"eras": [labels], "rows": [{"name":…, "cells": [state, …]}]}` where each
    cell is one of `born`, `here`, `alive`, `died`, `gone`, `unborn`, `unknown`.

    This is the view the writer asked for and the one no list of events can
    give: every character down the side, every era across the top, and the
    holes visible at a glance.
    """
    windows = eras(reading, span=span, era_label=era_label)
    if not windows:
        return {"eras": [], "rows": []}

    lives = existences(reading)
    people = sorted(n for n, e in lives.items() if e.kind == CHARACTER)

    rows = []
    for name in people:
        existence = lives[name]
        cells = []
        for era in windows:
            if existence.begins is not None and existence.begins > era.end:
                cells.append("unborn")
            elif existence.ends is not None and existence.ends < era.start:
                cells.append("gone")
            elif name in era.born:
                cells.append("born")
            elif name in era.died:
                cells.append("died")
            elif name in era.appears:
                cells.append("here")
            elif name in era.alive:
                cells.append("alive")
            else:
                cells.append("unknown")
        rows.append({"name": name, "cells": cells})

    return {"eras": [e.label for e in windows], "rows": rows}


def render_grid(grid):
    """The grid as fixed-width text. `#` on the page, `·` alive but offstage."""
    glyphs = {"born": "+", "here": "#", "alive": "·", "died": "x",
              "gone": " ", "unborn": " ", "unknown": "?"}
    if not grid["rows"]:
        return "(no dated characters)"

    width = max(len(row["name"]) for row in grid["rows"])
    lines = [" " * (width + 2) + "  ".join(str(i + 1).rjust(2)
                                           for i in range(len(grid["eras"])))]
    for row in grid["rows"]:
        cells = "   ".join(glyphs[c] for c in row["cells"])
        lines.append(f"{row['name'].ljust(width)}  {cells}")
    lines.append("")
    for i, label in enumerate(grid["eras"]):
        lines.append(f"  {i + 1}. {label}")
    lines.append("")
    lines.append("  + born   # on the page   · alive, offstage   x died")
    return "\n".join(lines)


__all__ = [
    "Era", "Circle", "eras", "cast_at", "co_presence", "circles",
    "generations", "timeline_grid", "render_grid",
]
