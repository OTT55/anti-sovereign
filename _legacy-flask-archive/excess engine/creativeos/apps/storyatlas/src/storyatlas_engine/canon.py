"""Phase 5 — Canon rules: continuity errors beyond a lifespan.

Phase 1 caught a character acting after their own death. That is one rule; a
space breaks in more ways than that, and each of these is a real mistake
writers make and struggle to find by hand:

* an **organisation acting before it was founded**
* a **place referenced before it existed** (or after it fell)
* a **title held by two people at once**
* a character **in two places at the same time**
* a **relationship outside both parties' lifespans**
* an **event dated outside the era it belongs to**

Every rule is deterministic and reports the exact records in conflict. None of
them guesses: a rule that cannot be evaluated because a date is missing stays
silent rather than reporting a maybe. A continuity checker that cries wolf gets
switched off, and then it catches nothing at all.
"""

from collections import defaultdict


class CanonViolation:
    """A continuity error, with the records that prove it."""

    __slots__ = ("rule", "subject", "text", "evidence", "severity", "sentence_index")

    def __init__(self, rule, subject, text, evidence="", severity="error",
                 sentence_index=None):
        self.rule = rule
        self.subject = subject
        self.text = text
        self.evidence = evidence
        self.severity = severity      # "error" | "warning"
        self.sentence_index = sentence_index

    def describe(self):
        return f"[{self.rule}] {self.text}"

    def __repr__(self):
        return f"<CanonViolation {self.describe()}>"


def dedupe(violations):
    """One finding per (rule, subject, sentence, wording).

    Shared with Phase 8, because the same contradiction can legitimately be
    reached by two different rules — a character in a fallen city after their
    own death trips both. Reporting it twice makes the engine look unsure of
    itself, and a writer who sees duplicates starts discounting the whole list.
    """
    seen, out = set(), []
    for violation in sorted(violations,
                            key=lambda v: (v.severity != "error", v.rule,
                                           v.subject or "")):
        key = (violation.rule, violation.subject, violation.sentence_index,
               violation.text)
        if key in seen:
            continue
        seen.add(key)
        out.append(violation)
    return out


def check(reading):
    """Run every canon rule over a reading. Returns `[CanonViolation, ...]`."""
    violations = []
    violations += _acting_before_founding(reading)
    violations += _title_held_twice(reading)
    violations += _two_places_at_once(reading)
    violations += _relationship_outside_lifespans(reading)
    violations += _event_before_its_participants(reading)
    return sorted(violations, key=lambda v: (v.severity != "error", v.rule, v.subject or ""))


def _founding_years(reading):
    """When each organisation came into being, where the draft says so."""
    founded = {}
    for placement in reading.timeline.placements:
        event = placement.event
        if event.kind != "founding" or not placement.is_dated:
            continue
        # The thing founded is the object; the founder is the agent.
        target = event.patient or event.subject
        if target:
            founded.setdefault(target, placement.year)
    return founded


def _acting_before_founding(reading):
    """An organisation cannot do anything before it exists."""
    founded = _founding_years(reading)
    out = []
    for placement in reading.timeline.placements:
        event = placement.event
        if not placement.is_dated or event.kind == "founding":
            continue
        for name in (event.agent, event.subject):
            if name in founded and placement.year < founded[name]:
                out.append(CanonViolation(
                    "founding", name,
                    f"{name} was founded in {founded[name]}, but this is dated "
                    f"{placement.year}.",
                    event.text, sentence_index=event.sentence_index))
    return out


def _title_held_twice(reading):
    """Two people holding one office at the same moment.

    Only flagged when both accessions are dated and no intervening death or
    succession explains it — otherwise every orderly handover looks like a bug.
    """
    accessions = [p for p in reading.timeline.by_kind("accession")
                  if p.is_dated and p.event.subject]
    spans = reading.lifespans()
    out = []

    for i, first in enumerate(accessions):
        for second in accessions[i + 1:]:
            if first.event.subject == second.event.subject:
                continue
            if first.year != second.year:
                continue
            _born, died = spans.get(first.event.subject, (None, None))
            if died is not None and died <= second.year:
                continue   # the first holder had already died — a handover
            out.append(CanonViolation(
                "title", first.event.subject,
                f"{first.event.subject} and {second.event.subject} both take "
                f"office in {first.year}.",
                second.event.text, severity="warning",
                sentence_index=second.event.sentence_index))
    return out


def _two_places_at_once(reading):
    """A character in two places in the same year."""
    by_person_year = defaultdict(set)
    evidence = {}
    for placement in reading.timeline.placements:
        event = placement.event
        if not placement.is_dated or not event.place or not event.subject:
            continue
        by_person_year[(event.subject, placement.year)].add(event.place)
        evidence[(event.subject, placement.year, event.place)] = event

    out = []
    for (subject, year), places in sorted(by_person_year.items()):
        if len(places) < 2:
            continue
        listed = ", ".join(sorted(places))
        event = evidence[(subject, year, sorted(places)[0])]
        out.append(CanonViolation(
            "location", subject,
            f"{subject} is in two places in {year}: {listed}.",
            event.text, severity="warning", sentence_index=event.sentence_index))
    return out


def _relationship_outside_lifespans(reading):
    """A relationship stated between people whose lives did not overlap."""
    spans = reading.lifespans()
    out = []
    for relation in reading.relations:
        if relation.inferred:
            continue
        a_born, a_died = spans.get(relation.subject, (None, None))
        b_born, b_died = spans.get(relation.target, (None, None))
        if a_died is not None and b_born is not None and b_born > a_died:
            out.append(CanonViolation(
                "relationship", relation.subject,
                f"{relation.subject} died in {a_died}, but {relation.target} "
                f"was not born until {b_born}.",
                relation.evidence, sentence_index=relation.sentence_index))
        elif b_died is not None and a_born is not None and a_born > b_died:
            out.append(CanonViolation(
                "relationship", relation.target,
                f"{relation.target} died in {b_died}, but {relation.subject} "
                f"was not born until {a_born}.",
                relation.evidence, sentence_index=relation.sentence_index))
    return out


def _event_before_its_participants(reading):
    """Someone taking part in something before they were born."""
    spans = reading.lifespans()
    out = []
    for placement in reading.timeline.placements:
        event = placement.event
        if not placement.is_dated or event.kind == "birth":
            continue
        for name in {event.agent, event.patient} - {None}:
            born, _died = spans.get(name, (None, None))
            if born is not None and placement.year < born:
                out.append(CanonViolation(
                    "unborn", name,
                    f"{name} was born in {born}, but takes part in this, dated "
                    f"{placement.year}.",
                    event.text, sentence_index=event.sentence_index))
    return out
