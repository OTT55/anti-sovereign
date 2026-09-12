"""Phase 6 — narrative structure: arcs, pacing, and setups that never pay off.

This is where the deterministic approach reaches its honest limit, so it is
worth being precise about what is and is not computable.

**Computable**, and done here:

* *presence* — where a character appears across the draft, and where they
  vanish for long stretches
* *pacing* — event density per stretch of text, which finds the sagging middle
* *setups without payoffs* — something introduced with weight and never
  mentioned again
* *arc shape* — whether a character's events cluster early, late, or throughout

**Not computable**, and not attempted: whether an arc is *satisfying*, whether
a theme *lands*, whether a reveal is *earned*. Those are judgements, and the
right answer is to say so rather than to dress a word-count up as insight. A
tool that reports "your protagonist disappears for 40% of the middle" is
useful. One that reports "your arc is unsatisfying" because a number crossed a
threshold is noise, and worse, it is noise a writer might believe.
"""

from collections import defaultdict


class Thread:
    """One character's presence through the draft."""

    __slots__ = ("name", "scenes", "events", "first_scene", "last_scene", "gaps")

    def __init__(self, name, scenes, events, first_scene, last_scene, gaps):
        self.name = name
        self.scenes = scenes
        self.events = events
        self.first_scene = first_scene
        self.last_scene = last_scene
        self.gaps = gaps

    @property
    def shape(self):
        """Where this character's presence sits in the draft.

        Descriptive, not evaluative — "front-loaded" is a fact about the text,
        whereas "badly paced" would be a judgement this cannot make.
        """
        if not self.scenes:
            return "absent"
        if len(self.scenes) == 1:
            return "single-appearance"
        span = self.last_scene - self.first_scene + 1
        density = len(self.scenes) / span if span else 1.0
        if density > 0.8:
            return "continuous"
        if self.gaps:
            return "intermittent"
        return "clustered"

    def describe(self):
        count = len(self.scenes)
        where = (f"scene {self.first_scene + 1}" if count == 1
                 else f"scenes {self.first_scene + 1}–{self.last_scene + 1}")
        return (f"{self.name}: {count} scene{'' if count == 1 else 's'} "
                f"({where}), {self.shape}")

    def __repr__(self):
        return f"<Thread {self.describe()}>"


class Observation:
    """Something factual about the shape of the draft."""

    __slots__ = ("kind", "subject", "text", "detail")

    def __init__(self, kind, subject, text, detail=None):
        self.kind = kind
        self.subject = subject
        self.text = text
        self.detail = detail or {}

    def describe(self):
        return f"[{self.kind}] {self.text}"

    def __repr__(self):
        return f"<Observation {self.describe()}>"


def threads(reading):
    """Each character's presence across the scenes."""
    appearances = defaultdict(list)
    for scene in reading.scenes:
        for name in scene.present:
            if reading.kind_of(name) == "character":
                appearances[name].append(scene.index)

    events_by_name = defaultdict(list)
    for placement in reading.timeline.placements:
        if placement.event.subject:
            events_by_name[placement.event.subject].append(placement)

    out = []
    for name, indices in appearances.items():
        gaps = []
        for a, b in zip(indices, indices[1:]):
            if b - a > 2:
                gaps.append((a, b))
        out.append(Thread(name, indices, events_by_name.get(name, []),
                          indices[0], indices[-1], gaps))
    return sorted(out, key=lambda t: (-len(t.scenes), t.name))


def pacing(reading, buckets=4):
    """Event density across the draft, in equal stretches of scenes.

    Finds the sagging middle by counting, not by opinion.
    """
    if not reading.scenes:
        return []
    size = max(1, len(reading.scenes) // buckets)
    out = []
    for i in range(0, len(reading.scenes), size):
        group = reading.scenes[i:i + size]
        events = sum(len(s.events) for s in group)
        out.append({
            "scenes": (group[0].index + 1, group[-1].index + 1),
            "events": events,
            "density": round(events / len(group), 2),
        })
    return out


def observations(reading):
    """Factual observations about the draft's shape."""
    out = []

    for thread in threads(reading):
        for start, end in thread.gaps:
            out.append(Observation(
                "absence", thread.name,
                f"{thread.name} is absent from scenes {start + 2}–{end}.",
                {"from": start + 1, "to": end}))

    # A character named once and never again: introduced with weight, dropped.
    for name, verdict in reading.types.items():
        if verdict.kind != "character":
            continue
        mentions = sum(1 for s in reading.scenes if name in s.present)
        if mentions == 1 and len(reading.scenes) > 2:
            out.append(Observation(
                "loose-end", name,
                f"{name} appears in only one scene and is never seen again.",
                {"scenes": mentions}))

    # A character with no recorded events is scenery, not a participant.
    for thread in threads(reading):
        if not thread.events and len(thread.scenes) > 1:
            out.append(Observation(
                "passive", thread.name,
                f"{thread.name} appears in {len(thread.scenes)} scenes but "
                "nothing is recorded as happening to them.",
                {"scenes": len(thread.scenes)}))

    density = pacing(reading)
    if len(density) >= 3:
        middle = density[1:-1]
        quietest = min(middle, key=lambda d: d["density"])
        busiest = max(density, key=lambda d: d["density"])
        if busiest["density"] > 0 and quietest["density"] < busiest["density"] / 2:
            out.append(Observation(
                "pacing", None,
                f"Scenes {quietest['scenes'][0]}–{quietest['scenes'][1]} carry "
                f"{quietest['density']} events per scene, against "
                f"{busiest['density']} at the busiest point.",
                {"quiet": quietest, "busy": busiest}))

    return out
