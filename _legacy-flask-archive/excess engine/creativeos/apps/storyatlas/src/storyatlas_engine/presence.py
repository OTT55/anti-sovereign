"""Phase 8 — reconciling people with places and time.

The gap this closes was reported from actually using the thing: *"there are
people supposed to be dead in the future, but they are alive, which makes no
sense."* That is true of the engine as it stood, and the reason is precise
rather than vague.

Up to Phase 7 a character's death was checked against **dated events naming
them as the grammatical subject**. Three ways of being alive after your own
death slipped straight through:

1. **Appearing in a scene.** Scenes had no resolved year at all, so a scene set
   in 1160 could list a character who died in 1147 and nothing compared the two.
2. **Being the object rather than the subject.** "The council summoned Aldric"
   makes Aldric the patient; the lifespan check never looked there.
3. **Standing in a place.** A place has a lifetime too — founded, fallen — and
   nothing reconciled a person's years against a location's.

So this module does three things, all arithmetic:

* **dates the scenes**, which nothing did before, by propagating event dates and
  scene-level time expressions the same way `solver.py` propagates event dates;
* builds a typed **existence interval** for every entity — people, places and
  organisations kept apart, because "Dawnhold fell in 1140" is a place ending,
  not a character dying;
* **intersects** those intervals with every appearance, and reports each empty
  intersection as a specific, evidenced contradiction.

An interval intersection is the whole trick. `[born, died] ∩ {year}` is either
empty or it is not, and there is nothing to infer, prompt or hallucinate.

One rule governs severity throughout: **a conclusion is only as strong as its
weakest date.** A scene dated by carrying the previous scene's year forward is a
reasonable assumption, not a fact, so contradictions resting on it are reported
as warnings. Only dates the text actually supports produce errors. A checker
that cries wolf gets switched off, and then it catches nothing at all.
"""

import re
from collections import defaultdict

from .canon import CanonViolation, dedupe
from .comprehend.typing import CHARACTER, EVENT, LOCATION, ORGANIZATION, UNKNOWN

#: Scene-date provenance, strongest first. Only the first three are firm enough
#: to accuse a draft of a continuity error.
FIRM = ("event", "stated", "computed")
SOFT = ("carried", "unknown")

#: A writer's marker that an anomaly is intentional — a flashback, a vision, a
#: ghost. Written into the draft rather than held in a database beside it, so
#: the exemption travels with the text, survives a copy-paste into another
#: editor, and is legible to a human reading the file. A suppression the writer
#: cannot see is one they will trip over again in six months.
DELIBERATE = re.compile(r"\[\s*deliberate\b[^\]]*\]", re.IGNORECASE)


class Existence:
    """When something exists: `[begins, ends]`, either end possibly open.

    Deliberately one type for people, places and organisations, because the
    reconciliation maths is identical — only the words differ. A character's
    interval is birth to death; a kingdom's is founding to fall.
    """

    __slots__ = ("name", "kind", "begins", "ends", "begins_evidence", "ends_evidence")

    def __init__(self, name, kind, begins=None, ends=None,
                 begins_evidence="", ends_evidence=""):
        self.name = name
        self.kind = kind
        self.begins = begins
        self.ends = ends
        self.begins_evidence = begins_evidence
        self.ends_evidence = ends_evidence

    def contains(self, year):
        """Is `year` inside this interval? `None` when it cannot be decided.

        Three-valued on purpose. An unknown answer must not collapse into
        "fine" — that is how a checker quietly stops checking — nor into
        "broken", which would flag every character whose birth is never stated.
        """
        if year is None:
            return None
        if self.begins is None and self.ends is None:
            return None
        if self.begins is not None and year < self.begins:
            return False
        if self.ends is not None and year > self.ends:
            return False
        return True

    def overlaps(self, other):
        """Could these two have coexisted? `None` when undecidable."""
        if self.ends is not None and other.begins is not None and other.begins > self.ends:
            return False
        if other.ends is not None and self.begins is not None and self.begins > other.ends:
            return False
        if (self.begins is None and self.ends is None) or \
           (other.begins is None and other.ends is None):
            return None
        return True

    @property
    def is_bounded(self):
        return self.begins is not None or self.ends is not None

    def describe(self):
        opens = self.begins if self.begins is not None else "?"
        closes = self.ends if self.ends is not None else "?"
        verb = {LOCATION: "standing", ORGANIZATION: "active"}.get(self.kind, "alive")
        return f"{self.name} ({self.kind}) {verb} {opens}–{closes}"

    def __repr__(self):
        return f"<Existence {self.describe()}>"


class SceneDate:
    """A scene's position in time, and how firmly it was arrived at.

    Carries a **span**, not just a point. A scene that narrates a birth in 1102
    and a founding in 1090 covers thirteen years, and collapsing that to one
    number then checking who was alive "at" it produces nonsense — a character
    is flagged as appearing before their own birth in the very scene that
    narrates it. `year` is the scene's position for ordering; `low`/`high` are
    what any liveness check must use.
    """

    __slots__ = ("scene_index", "year", "source", "evidence", "low", "high")

    def __init__(self, scene_index, year=None, source="unknown", evidence="",
                 low=None, high=None):
        self.scene_index = scene_index
        self.year = year
        self.source = source
        self.evidence = evidence
        self.low = low if low is not None else year
        self.high = high if high is not None else year

    @property
    def is_firm(self):
        """Firm enough to call a contradiction an error rather than a warning."""
        return self.year is not None and self.source in FIRM

    @property
    def spans_years(self):
        return self.low is not None and self.high is not None and self.high > self.low

    def describe(self):
        if self.year is None:
            return f"Scene {self.scene_index + 1}: undated"
        span = f"–{self.high}" if self.spans_years else ""
        return f"Scene {self.scene_index + 1}: {self.year}{span} ({self.source})"

    def __repr__(self):
        return f"<SceneDate {self.describe()}>"


class Appearance:
    """One moment of somebody being somewhere, and how we know."""

    __slots__ = ("who", "year", "place", "via", "firm", "evidence", "sentence_index",
                 "scene_index", "low", "high", "deliberate")

    def __init__(self, who, year, place=None, via="event", firm=True, evidence="",
                 sentence_index=None, scene_index=None, low=None, high=None,
                 deliberate=False):
        self.who = who
        self.year = year
        self.place = place
        self.via = via            # "event" | "scene"
        self.firm = firm
        self.evidence = evidence
        self.sentence_index = sentence_index
        self.scene_index = scene_index
        #: The window this appearance could fall in. Equal to `year` for an
        #: event, which happens at one moment; wider for a scene, which does
        #: not. A liveness check must clear the *whole* window before it
        #: accuses the draft of anything.
        self.low = low if low is not None else year
        self.high = high if high is not None else year
        #: The writer has marked this anomaly intentional in the text itself.
        self.deliberate = deliberate

    def describe(self):
        where = f" at {self.place}" if self.place else ""
        return f"{self.who} in {self.year}{where} (via {self.via})"

    def __repr__(self):
        return f"<Appearance {self.describe()}>"


# ---------------------------------------------------------------------------
# Dating the scenes
# ---------------------------------------------------------------------------

def date_scenes(reading):
    """Put every scene on the timeline. Returns `[SceneDate, ...]`.

    Four sources, strongest first, and each scene records which one it used:

    * **event** — the earliest dated event inside the scene. Strongest, because
      it is the solver's own arithmetic and the event is demonstrably in this
      scene.
    * **stated** — the scene's own time expression, when it names a year.
    * **computed** — a relative expression ("three years later") resolved
      against the previous scene, which is what the phrase means in prose.
    * **carried** — no time signal at all, so the previous scene's year is
      assumed. Prose does this constantly, but it is an assumption and is
      marked as one so nothing downstream treats it as evidence.
    """
    placement_by_event = {id(p.event): p for p in reading.timeline.placements}
    dates = []
    previous = None

    for scene in reading.scenes:
        years = [placement_by_event[id(e)].year for e in scene.events
                 if id(e) in placement_by_event and placement_by_event[id(e)].is_dated]

        if years:
            date = SceneDate(scene.index, min(years), "event", scene.title,
                             low=min(years), high=max(years))
        elif scene.time is not None and scene.time.kind == "absolute":
            date = SceneDate(scene.index, scene.time.value, "stated", scene.time.text)
        elif scene.time is not None and previous is not None and \
                scene.time.kind in ("offset", "same"):
            delta = scene.time.value if scene.time.kind == "offset" else 0
            date = SceneDate(scene.index, previous + (delta or 0), "computed",
                             scene.time.text)
        elif previous is not None:
            date = SceneDate(scene.index, previous, "carried",
                             "no time given; assumed to follow the previous scene")
        else:
            date = SceneDate(scene.index, None, "unknown", "")

        if date.year is not None:
            previous = date.year
        dates.append(date)

    return dates


# ---------------------------------------------------------------------------
# Typed existence intervals
# ---------------------------------------------------------------------------

def existences(reading):
    """`{name: Existence}` for every named thing, typed.

    Typing matters more here than anywhere else in the engine. The extractor
    turns *"Dawnhold fell in 1140"* into a `death` event whose subject is
    Dawnhold, exactly as it turns *"Aldric fell in 1147"* into one. Untyped,
    both land in the same lifespan table and a place acquires a date of death —
    after which the engine will happily complain that a character was born after
    a castle died. Splitting them by entity kind is what makes the reconciliation
    mean anything.
    """
    found = {}

    # Anything the extractor put in an event's `place` slot is a place. That is
    # stronger evidence than the surface cues typing works from — the sentence
    # said *at Dawnhold*, and only a location follows "at" that way. Typing
    # often lands on "other" for a name mentioned two or three times, and an
    # untyped place is silently exempt from every rule about places, so the
    # reconciliation quietly stops checking exactly the entities it was built
    # for. Filling the gap here leaves `types` untouched and honest about what
    # its own evidence supported.
    as_place = {p.event.place for p in reading.timeline.placements if p.event.place}
    as_place |= {s.place for s in reading.scenes if s.place}

    def slot(name):
        if name not in found:
            kind = reading.kind_of(name)
            if kind == UNKNOWN and name in as_place:
                kind = LOCATION
            found[name] = Existence(name, kind)
        return found[name]

    for placement in reading.timeline.placements:
        event = placement.event
        if not placement.is_dated:
            continue

        # A founding dates the thing founded, not the founder.
        if event.kind == "founding":
            target = event.patient or event.subject
            if target:
                existence = slot(target)
                if existence.begins is None:
                    existence.begins, existence.begins_evidence = placement.year, event.text
            continue

        subject = event.subject
        if not subject:
            continue
        kind = reading.kind_of(subject)
        existence = slot(subject)

        if event.kind == "birth" and kind in (CHARACTER, UNKNOWN):
            if existence.begins is None:
                existence.begins, existence.begins_evidence = placement.year, event.text
        elif event.kind == "death":
            # For a place or an organisation this is a fall, not a death — the
            # same arithmetic, a different word, and only the word changes.
            if existence.ends is None:
                existence.ends, existence.ends_evidence = placement.year, event.text

    return found


def character_lifespans(reading):
    """Lifespans for people only — `{name: (born, died)}`.

    `Reading.lifespans()` returns the raw solver output, which is untyped and
    therefore includes fallen cities. Anything reasoning about *people* should
    use this.
    """
    return {name: (e.begins, e.ends)
            for name, e in existences(reading).items()
            if e.kind == CHARACTER and e.is_bounded}


# ---------------------------------------------------------------------------
# Where everybody is
# ---------------------------------------------------------------------------

def appearances(reading, scene_dates=None):
    """Every moment the draft puts a named person somewhere in time.

    Both routes are collected, and that is the point — the second one is what
    the engine was missing:

    * **events** — anyone named as agent *or* patient. Checking only the
      grammatical subject misses "the council summoned Aldric", where Aldric
      does nothing yet is unambiguously present.
    * **scenes** — anyone listed in a dated scene. A character standing in a
      scene set thirteen years after their funeral is the failure that prompted
      all this, and it is invisible unless scene presence is checked directly.
    """
    scene_dates = scene_dates if scene_dates is not None else date_scenes(reading)
    by_index = {d.scene_index: d for d in scene_dates}
    out = []

    for placement in reading.timeline.placements:
        event = placement.event
        if not placement.is_dated:
            continue
        for name in _ordered_unique((event.agent, event.patient)):
            if reading.kind_of(name) != CHARACTER:
                continue
            out.append(Appearance(
                who=name, year=placement.year, place=event.place, via="event",
                firm=placement.source in ("stated", "computed"),
                evidence=event.text, sentence_index=event.sentence_index,
                deliberate=bool(DELIBERATE.search(event.text))))

    for scene in reading.scenes:
        date = by_index.get(scene.index)
        if date is None or date.year is None:
            continue
        for name in scene.present:
            if reading.kind_of(name) != CHARACTER:
                continue
            # Point at the sentence that actually names them, not at the scene
            # heading. A finding a writer cannot navigate to is a finding they
            # will not act on — and every offered fix edits a sentence, so a
            # finding with no sentence has no fix that does anything.
            sentence = _sentence_naming(reading, scene, name)
            out.append(Appearance(
                who=name, year=date.year, place=scene.place, via="scene",
                firm=date.is_firm,
                evidence=sentence.text if sentence else scene.title,
                sentence_index=sentence.index if sentence else None,
                scene_index=scene.index, low=date.low, high=date.high,
                deliberate=bool(DELIBERATE.search(
                    sentence.text if sentence else scene.text))))

    return out


def _sentence_naming(reading, scene, name):
    """The first sentence inside a scene that mentions a given name.

    Containment in the scene's own text is the test, not `sentence_range`.
    The range is derived by counting sentences per block and drifts whenever a
    heading or a marker line is counted differently from the sentence splitter
    — which points the fix at a sentence in the wrong chapter. The scene's text
    is exact, so matching against it cannot drift.
    """
    for sentence in reading.sentences:
        body = sentence.text.strip()
        if name in body and body[:60] in scene.text:
            return sentence
    start, end = scene.sentence_range
    for sentence in reading.sentences[start:end]:
        if name in sentence.text:
            return sentence
    return None


def itinerary(reading, name, scene_dates=None):
    """One character's movements: `[(year, place), ...]` in order.

    The per-person view of the reconciliation — where somebody is, when.
    """
    seen = []
    for appearance in appearances(reading, scene_dates):
        if appearance.who != name or appearance.place is None:
            continue
        step = (appearance.year, appearance.place)
        if step not in seen:
            seen.append(step)
    return sorted(seen, key=lambda s: s[0])


def occupancy(reading, scene_dates=None):
    """The mirror image: `{place: {year: [names]}}` — who was where, when."""
    out = defaultdict(lambda: defaultdict(list))
    for appearance in appearances(reading, scene_dates):
        if appearance.place is None:
            continue
        people = out[appearance.place][appearance.year]
        if appearance.who not in people:
            people.append(appearance.who)
    return {place: {year: sorted(names) for year, names in sorted(years.items())}
            for place, years in sorted(out.items())}


# ---------------------------------------------------------------------------
# The reconciliation itself
# ---------------------------------------------------------------------------

def reconcile(reading):
    """Check every appearance against every existence interval.

    Returns `[CanonViolation, ...]` — the same type Phase 5 produces, so the
    report treats these as continuity errors rather than as a separate species
    of finding a writer would have to learn to read.
    """
    scene_dates = date_scenes(reading)
    lives = existences(reading)

    # A flashback, a vision and a ghost are all real techniques, and a checker
    # that cannot be told "yes, I meant that" is one a writer switches off.
    moments = [m for m in appearances(reading, scene_dates) if not m.deliberate]

    violations = []
    violations += _outside_own_lifetime(moments, lives)
    violations += _in_a_place_that_did_not_exist(moments, lives)
    violations += _impossible_meetings(reading, scene_dates, lives)
    violations += _in_two_places(moments)
    return dedupe(violations)


def _outside_own_lifetime(moments, lives):
    """Alive before birth, or alive after death. The headline rule.

    Checked against the appearance's whole window, so a contradiction is only
    reported when *no* point in it works. For an event that is a single year and
    the check is exact; for a scene covering a stretch of years it is the
    difference between a real finding and accusing a birth scene of featuring
    someone before they were born.
    """
    out = []
    for moment in moments:
        existence = lives.get(moment.who)
        if existence is None or not existence.is_bounded:
            continue
        if not _window_conflicts(existence, moment.low, moment.high):
            continue

        severity = "error" if moment.firm else "warning"
        if existence.ends is not None and moment.year > existence.ends:
            gap = moment.year - existence.ends
            where = (f"scene {moment.scene_index + 1}" if moment.via == "scene"
                     else "this")
            hedge = "" if moment.firm else " (on an assumed date — worth confirming)"
            out.append(CanonViolation(
                "posthumous", moment.who,
                f"{moment.who} died in {existence.ends}, but appears in {where}, "
                f"dated {moment.year} — {gap} year{'s' if gap != 1 else ''} later."
                f"{hedge}",
                moment.evidence, severity=severity,
                sentence_index=moment.sentence_index))
        elif existence.begins is not None and moment.year < existence.begins:
            gap = existence.begins - moment.year
            hedge = "" if moment.firm else " (on an assumed date — worth confirming)"
            out.append(CanonViolation(
                "prenatal", moment.who,
                f"{moment.who} was born in {existence.begins}, but appears here, "
                f"dated {moment.year} — {gap} year{'s' if gap != 1 else ''} "
                f"earlier.{hedge}",
                moment.evidence, severity=severity,
                sentence_index=moment.sentence_index))
    return out


def _window_conflicts(existence, low, high):
    """Can `[low, high]` and this existence interval share no year at all?

    The one predicate the whole reconciliation rests on. Two intervals conflict
    only when one ends strictly before the other begins; anything else — an
    overlap, a touch, an open end, a missing date — is not a contradiction and
    must not be reported as one.
    """
    if low is None or high is None:
        return False
    if existence.ends is not None and low > existence.ends:
        return True
    if existence.begins is not None and high < existence.begins:
        return True
    return False


def _in_a_place_that_did_not_exist(moments, lives):
    """Somebody standing somewhere before it was built or after it fell.

    The other half of "reconcile places with people": a place has a lifetime
    too, and a person's year has to fit inside it.
    """
    out = []
    for moment in moments:
        if moment.place is None:
            continue
        place = lives.get(moment.place)
        if place is None or place.kind not in (LOCATION, ORGANIZATION):
            continue
        if not _window_conflicts(place, moment.low, moment.high):
            continue

        severity = "error" if moment.firm else "warning"
        if place.ends is not None and moment.year > place.ends:
            gone = "fell" if place.kind == LOCATION else "was dissolved"
            out.append(CanonViolation(
                "place-gone", moment.place,
                f"{moment.place} {gone} in {place.ends}, but {moment.who} is "
                f"there in {moment.year}.",
                moment.evidence, severity=severity,
                sentence_index=moment.sentence_index))
        elif place.begins is not None and moment.year < place.begins:
            built = "was founded" if place.kind == LOCATION else "was formed"
            out.append(CanonViolation(
                "place-not-yet", moment.place,
                f"{moment.place} {built} in {place.begins}, but {moment.who} is "
                f"there in {moment.year}.",
                moment.evidence, severity=severity,
                sentence_index=moment.sentence_index))
    return out


def _impossible_meetings(reading, scene_dates, lives):
    """Two people sharing a scene whose lifetimes never overlapped.

    Distinct from the lifespan rule, and not implied by it: a scene can be
    undated, so neither character is individually out of place, and yet the two
    of them provably could not have been in a room together. That is a fact
    about the *pair*, and only a pairwise check finds it.
    """
    by_index = {d.scene_index: d for d in scene_dates}
    out = []

    for scene in reading.scenes:
        if DELIBERATE.search(scene.text):
            continue
        people = [n for n in scene.present if reading.kind_of(n) == CHARACTER]
        for i, first in enumerate(people):
            for second in people[i + 1:]:
                a, b = lives.get(first), lives.get(second)
                if a is None or b is None:
                    continue
                if a.overlaps(b) is not False:
                    continue
                date = by_index.get(scene.index)
                dated = f" (scene {scene.index + 1}"
                dated += f", dated {date.year})" if date and date.year else ")"
                earlier, later = (a, b) if (a.ends or 0) <= (b.begins or 0) else (b, a)
                out.append(CanonViolation(
                    "impossible-meeting", first,
                    f"{first} and {second} share a scene{dated}, but "
                    f"{earlier.name} died in {earlier.ends} and {later.name} was "
                    f"not born until {later.begins}.",
                    scene.title, severity="error"))
    return out


def _in_two_places(moments):
    """One person, one year, two places — from scenes as well as events.

    A warning rather than an error: a year is a coarse unit and a character can
    honestly travel within one. What makes it worth saying is that it is often
    the visible symptom of a date that is wrong somewhere else.
    """
    grouped = defaultdict(dict)
    for moment in moments:
        if moment.place is None:
            continue
        grouped[(moment.who, moment.year)].setdefault(moment.place, moment)

    out = []
    for (who, year), places in sorted(grouped.items()):
        if len(places) < 2:
            continue
        first = places[sorted(places)[0]]
        out.append(CanonViolation(
            "bilocation", who,
            f"{who} is in {' and '.join(sorted(places))} in the same year "
            f"({year}).",
            first.evidence, severity="warning",
            sentence_index=first.sentence_index))
    return out


def _ordered_unique(names):
    out = []
    for name in names:
        if name and name not in out:
            out.append(name)
    return out


__all__ = [
    "Existence", "SceneDate", "Appearance",
    "date_scenes", "existences", "character_lifespans",
    "appearances", "itinerary", "occupancy", "reconcile",
    "CHARACTER", "LOCATION", "ORGANIZATION", "EVENT", "UNKNOWN",
]
