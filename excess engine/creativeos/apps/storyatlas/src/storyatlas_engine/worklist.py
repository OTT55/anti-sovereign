"""Phase 9 — turning understanding into something a writer can *do*.

The question this answers is the blunt one: *you have all the facts about my
draft — so what? What do I actually do with it?*

Phase 7's report is a list of findings. A list is not a plan. Thirty findings in
severity order still leaves the writer to work out which one to touch first, and
the honest answer is not "the most severe" — it is **the one the most other
findings hang off.**

That is computable, and it is the whole idea here.

## Leverage

When the solver dates an event by arithmetic, it does so against an anchor. Fix
a wrong anchor and every date computed from it moves with it. So a stated year
that anchors nine computed dates is worth nine times a stated year that anchors
none — and three separate contradictions downstream may all be one wrong number
upstream.

`leverage` counts exactly that: the computed placements that depend on this one,
the lifespans it bounds, and the contradictions that would resolve if it changed.
It is a count of real dependencies, not a score, so it can be shown to the
writer and checked.

## Every fix carries its options

A finding that says "this is wrong" makes the writer do the work again. Each
`Fix` here carries concrete `Action`s — set this year, name this pronoun, record
this death, strike this clause — and each one can be previewed and applied by
`revise.py`. Choosing from three options is a fraction of the work of deciding
what to type.

Nothing here edits anything. This module decides *what is worth doing and in
what order*; `revise.py` does it.
"""

import re

from .comprehend.typing import CHARACTER
from .presence import date_scenes, existences

#: Ordering of severities. Errors are contradictions; warnings are suspicions;
#: gaps are things merely absent; notes are observations about shape.
SEVERITY_ORDER = {"error": 0, "warning": 1, "gap": 2, "note": 3}

_YEAR = re.compile(r"\b(\d{3,4})\b")


class Action:
    """One concrete, applicable change.

    `kind` is what `revise.py` knows how to perform:

    * `set-year`      — replace the year in a sentence
    * `name`          — replace a pronoun with a name
    * `annotate`      — add a bracketed note, changing nothing but the record
    * `strike`        — remove the sentence
    * `record-death`  — append an explicit death year for a character
    * `accept`        — confirm the engine's reading; no text change
    * `dismiss`       — this is intentional; stop reporting it
    """

    __slots__ = ("kind", "label", "sentence_index", "payload", "consequence")

    def __init__(self, kind, label, sentence_index=None, payload=None,
                 consequence=""):
        self.kind = kind
        self.label = label
        self.sentence_index = sentence_index
        self.payload = payload or {}
        self.consequence = consequence

    def __repr__(self):
        return f"<Action {self.kind}: {self.label}>"


class Fix:
    """One thing worth doing, with the options for doing it."""

    __slots__ = ("id", "severity", "rule", "title", "subject", "evidence",
                 "sentence_index", "options", "leverage", "why")

    def __init__(self, id, severity, rule, title, subject=None, evidence="",
                 sentence_index=None, options=None, leverage=0, why=""):
        self.id = id
        self.severity = severity
        self.rule = rule
        self.title = title
        self.subject = subject
        self.evidence = evidence
        self.sentence_index = sentence_index
        self.options = options or []
        self.leverage = leverage
        self.why = why

    @property
    def rank(self):
        """Sort key: severity first, then how much else depends on it."""
        return (SEVERITY_ORDER.get(self.severity, 9), -self.leverage,
                self.sentence_index if self.sentence_index is not None else 10**6)

    def describe(self):
        weight = f"  [{self.leverage} depend]" if self.leverage else ""
        return f"[{self.severity}] {self.title}{weight}"

    def __repr__(self):
        return f"<Fix {self.describe()}>"


# ---------------------------------------------------------------------------
# Leverage
# ---------------------------------------------------------------------------

def dependents(reading, sentence_index):
    """How many facts rest on the date in this sentence.

    Three kinds of dependency, all real:

    * **computed dates** — placements the solver derived by chaining forward
      from this one, up to the next independently stated date. Those are
      precisely the events whose years move if this year moves.
    * **lifespans** — a birth or death here bounds a character, and every
      appearance of that character is checked against the bound.
    * **scenes** — scenes dated by carrying this year forward.

    Deliberately a count of things, not a weighting. A number a writer can
    verify by looking beats a score they have to trust.
    """
    placements = reading.timeline.placements
    position = next((i for i, p in enumerate(placements)
                     if p.event.sentence_index == sentence_index and p.is_dated),
                    None)
    if position is None:
        return 0

    count = 0
    for later in placements[position + 1:]:
        if not later.is_dated:
            continue
        if later.source == "stated":
            break          # a fresh anchor; the chain stops here
        if later.source == "computed":
            count += 1

    subject = placements[position].event.subject
    if subject and placements[position].event.kind in ("birth", "death"):
        count += sum(1 for p in placements
                     if p.is_dated and subject in (p.event.agent, p.event.patient))
        count += sum(1 for s in reading.scenes if subject in s.present)

    return count


# ---------------------------------------------------------------------------
# Building the worklist
# ---------------------------------------------------------------------------

def worklist(report, limit=None):
    """Everything worth doing to this draft, in the order worth doing it.

    Takes a `Report` (Phase 7) and returns `[Fix, ...]`.
    """
    reading = report.reading
    fixes = []
    fixes += _from_violations(reading, report.violations)
    fixes += _from_questions(reading)
    fixes += _from_observations(report.observations)

    fixes.sort(key=lambda f: f.rank)
    for i, fix in enumerate(fixes):
        fix.id = f"F{i + 1:02d}"
    return fixes[:limit] if limit else fixes


def _from_violations(reading, violations):
    """A contradiction always has at least two possible resolutions.

    Which of the two dates is wrong is a decision only the author can make, so
    both are offered rather than one being picked. An engine that silently
    chooses has invented a fact.
    """
    out = []
    lives = existences(reading)

    for violation in violations:
        leverage = (dependents(reading, violation.sentence_index)
                    if violation.sentence_index is not None else 0)
        options = []

        if violation.rule in ("posthumous", "prenatal", "lifespan"):
            existence = lives.get(violation.subject)
            bound = existence.ends if violation.rule == "posthumous" else existence.begins \
                if existence else None
            death_sentence = _sentence_of(reading, violation.subject,
                                          "death" if violation.rule == "posthumous"
                                          else "birth")
            if bound is not None and death_sentence is not None:
                options.append(Action(
                    "set-year", f"Move {violation.subject}'s "
                    f"{'death' if violation.rule == 'posthumous' else 'birth'} "
                    f"(currently {bound})",
                    sentence_index=death_sentence,
                    payload={"current": bound},
                    consequence=f"re-dates every check against {violation.subject}"))
            options.append(Action(
                "set-year", "Re-date this scene instead",
                sentence_index=violation.sentence_index,
                consequence="moves this event; leaves the lifespan alone"))
            options.append(Action(
                "annotate", "Mark it deliberate (a flashback, a vision, a ghost)",
                sentence_index=violation.sentence_index,
                payload={"note": "deliberate: outside lifespan"},
                consequence="keeps the text; stops the engine reporting it"))

        elif violation.rule in ("place-gone", "place-not-yet"):
            options.append(Action(
                "set-year", f"Re-date {violation.subject}'s founding or fall",
                sentence_index=_sentence_of(reading, violation.subject, None),
                consequence=f"changes every visit to {violation.subject}"))
            options.append(Action(
                "set-year", "Re-date this appearance",
                sentence_index=violation.sentence_index))
            options.append(Action(
                "annotate", "Mark it deliberate (a ruin, a memory, a rebuilding)",
                sentence_index=violation.sentence_index,
                payload={"note": "deliberate: outside the place's lifetime"}))

        elif violation.rule == "impossible-meeting":
            options.append(Action(
                "annotate", "Mark it deliberate (a flashback, a dream, a hallucination)",
                sentence_index=violation.sentence_index,
                payload={"note": "deliberate: characters from different eras"}))
            options.append(Action(
                "strike", "Remove one of them from the scene",
                sentence_index=violation.sentence_index,
                consequence="changes who is present; may orphan their dialogue"))

        elif violation.rule == "bilocation":
            options.append(Action(
                "annotate", "They travelled — say so",
                sentence_index=violation.sentence_index,
                payload={"note": "travelled between these within the year"}))
            options.append(Action(
                "set-year", "One of these two dates is wrong",
                sentence_index=violation.sentence_index))

        options.append(Action("dismiss", "Intentional — stop reporting this",
                              sentence_index=violation.sentence_index))

        out.append(Fix(
            id="", severity=violation.severity, rule=violation.rule,
            title=violation.text, subject=violation.subject,
            evidence=violation.evidence, sentence_index=violation.sentence_index,
            options=options, leverage=leverage,
            why=_why(violation.rule, leverage)))
    return out


def _from_questions(reading):
    """Unknowns, as gaps rather than errors.

    A missing date makes a draft incomplete; a contradiction makes it wrong.
    Ranking them together teaches a writer to skim the list, which costs more
    than the findings are worth.
    """
    out = []
    for question in reading.questions:
        # Both of these are now proper contradictions rather than open
        # questions — `conflict` since Phase 2, `lifespan` since Phase 8's
        # reconciliation. `read()` still raises them so it stands alone, but
        # listing them here as well would show a writer the same problem twice
        # under two different headings.
        if question.kind in ("conflict", "lifespan"):
            continue
        leverage = (dependents(reading, question.sentence_index)
                    if question.sentence_index is not None else 0)
        options = []

        if question.kind == "when":
            options.append(Action(
                "set-year", "Give it a year",
                sentence_index=question.sentence_index,
                consequence="dates this and anything the solver chains off it"))
            options.append(Action(
                "accept", "Leave it undated — the order is enough",
                sentence_index=question.sentence_index))
        elif question.kind == "pronoun":
            for name in question.options[:4]:
                options.append(Action(
                    "name", f"It means {name}",
                    sentence_index=question.sentence_index,
                    payload={"name": name},
                    consequence=f"attributes this to {name}"))
        elif question.kind == "type":
            for candidate in question.options[:4]:
                options.append(Action(
                    "confirm-type", f"{question.about} is a {candidate}",
                    payload={"name": question.about, "kind": candidate},
                    consequence="changes which rules apply to it"))
        elif question.kind == "who":
            for name in question.options[:4]:
                options.append(Action(
                    "name", f"It is {name}",
                    sentence_index=question.sentence_index,
                    payload={"name": name}))
        elif question.kind == "not-asserted":
            options.append(Action(
                "accept", "Correct — do not record it",
                sentence_index=question.sentence_index))
            options.append(Action(
                "annotate", "It did happen — record it",
                sentence_index=question.sentence_index,
                payload={"note": "confirmed as fact"}))

        options.append(Action("dismiss", "Not worth deciding",
                              sentence_index=question.sentence_index))

        out.append(Fix(
            id="", severity="gap", rule=question.kind, title=question.text,
            subject=question.about, evidence=question.evidence,
            sentence_index=question.sentence_index, options=options,
            leverage=leverage, why=_why(question.kind, leverage)))
    return out


def _from_observations(observations):
    """Shape, not correctness. Nothing here is wrong; some of it is worth
    knowing."""
    return [
        Fix(id="", severity="note", rule=o.kind, title=o.text, subject=o.subject,
            options=[Action("dismiss", "Noted")], leverage=0,
            why="A fact about the draft's shape, not a mistake.")
        for o in observations
    ]


def _sentence_of(reading, subject, kind):
    """Which sentence records a given fact about a name — so a fix can point at
    the cause rather than at the symptom."""
    if not subject:
        return None
    for placement in reading.timeline.placements:
        event = placement.event
        if event.subject != subject:
            continue
        if kind is None or event.kind == kind:
            return event.sentence_index
    return None


def _why(rule, leverage):
    base = {
        "posthumous": "A character is on the page after they died. Either the "
                      "death date or this scene's date is wrong.",
        "prenatal": "A character is on the page before they were born.",
        "place-gone": "Somebody is standing in a place the draft has already "
                      "destroyed.",
        "place-not-yet": "Somebody is standing in a place the draft has not "
                         "built yet.",
        "impossible-meeting": "Two characters share a scene although their "
                              "lifetimes never overlapped.",
        "bilocation": "One character, one year, two places. Often the visible "
                      "symptom of a wrong date elsewhere.",
        "when": "Undated. It still has a position in the narrative, but nothing "
                "can be checked against it.",
        "pronoun": "The engine guessed who this refers to and wants that "
                   "confirmed rather than assumed.",
        "type": "The engine cannot tell what kind of thing this is, and the "
                "rules that apply depend on the answer.",
    }.get(rule, "")
    if leverage:
        base += (f" {leverage} other fact{'s' if leverage != 1 else ''} in the "
                 f"draft depend{'' if leverage != 1 else 's'} on this one.")
    return base.strip()


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render(fixes, limit=12):
    """The worklist as text a writer can work down."""
    if not fixes:
        return "Nothing to fix. Every check passed and nothing is unresolved."

    counts = {}
    for fix in fixes:
        counts[fix.severity] = counts.get(fix.severity, 0) + 1
    header = " · ".join(f"{n} {s}{'s' if n != 1 else ''}"
                        for s, n in sorted(counts.items(),
                                           key=lambda kv: SEVERITY_ORDER.get(kv[0], 9)))

    lines = ["# What to do next", "", header, ""]
    for fix in fixes[:limit]:
        where = (f"  (sentence {fix.sentence_index + 1})"
                 if fix.sentence_index is not None else "")
        lines.append(f"## {fix.id}  {fix.title}{where}")
        if fix.leverage:
            lines.append(f"    {fix.leverage} other fact(s) depend on this.")
        if fix.evidence:
            lines.append(f"    “{fix.evidence.strip()[:80]}”")
        if fix.why:
            lines.append(f"    {fix.why}")
        for i, option in enumerate(fix.options):
            tail = f" — {option.consequence}" if option.consequence else ""
            lines.append(f"      {i + 1}. {option.label}{tail}")
        lines.append("")

    if len(fixes) > limit:
        lines.append(f"…and {len(fixes) - limit} more.")
    return "\n".join(lines).strip()


def next_action(fixes):
    """The single highest-leverage thing to do right now, or `None`.

    Exists because "here are forty findings" is not an answer to "what do I do
    next", and the whole point of ranking is being able to name one.
    """
    for fix in fixes:
        actionable = [o for o in fix.options if o.kind not in ("dismiss", "accept")]
        if actionable:
            return fix, actionable[0]
    return None


__all__ = ["Action", "Fix", "worklist", "dependents", "render", "next_action",
           "SEVERITY_ORDER"]
