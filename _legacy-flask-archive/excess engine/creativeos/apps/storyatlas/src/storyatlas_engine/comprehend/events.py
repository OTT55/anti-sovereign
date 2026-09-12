"""Turning a clause into a structured event: what happened, and to whom.

The gap this closes: the current Story Atlas stores an event as the raw sentence
plus a keyword-guessed category. That is a label on a string. Nothing links the
event to the people in it, so "who died?" cannot be answered, and deaths cannot
be grouped, ordered, or checked against anything.

Here an event is `(kind, agent, patient, place, time)`. Once a death knows
*whose* death it is, everything downstream becomes possible: lifespans, grouping
by person, and the contradiction checks CreativeOS already performs.

Role assignment uses English word order rather than a parser. In an active
clause the agent precedes the verb and the patient follows it; a passive
("was killed by") swaps them. That is a heuristic, and it is wrong on genuinely
tangled sentences — so every event carries a confidence, and a low-confidence
event becomes a question for the writer instead of a silent assertion.
"""

import re

from .factuality import classify as classify_factuality

# Each trigger: (regex, event kind, whether the surface form is passive).
# Passive matters because "Aldric killed Mara" and "Aldric was killed by Mara"
# name the same two people in the same order and mean opposite things.
#
# ORDER IS LOAD-BEARING. The first pattern to match wins, and a passive form
# contains its own active form — "was betrayed" contains "betrayed". Every
# passive variant must therefore be listed *before* its active counterpart, or
# the active one matches first and the roles come out reversed.
TRIGGERS = [
    (r"\bwas\s+(?:killed|slain|murdered|assassinated|executed)\b", "death", True),
    # "perishes" is here because spaCy's small model mis-tags it as a NOUN
    # (lemma "perishe"), so the lemma tier cannot catch it — a good example of
    # why the two tiers are complementary rather than one superseding the other.
    (r"\b(?:died|dies|perished|perishes|fell|falls)\b", "death", False),
    (r"\b(?:killed|slew|murdered|assassinated|executed)\b", "death", False),
    (r"\bdeath\s+of\b", "death", True),
    (r"\bwas\s+born\b", "birth", True),
    (r"\bbirth\s+of\b", "birth", True),
    (r"\b(?:married|wed|betrothed\s+to)\b", "marriage", False),
    (r"\bwas\s+crowned\b", "accession", True),
    (r"\b(?:took|ascended|claimed)\s+the\s+throne\b", "accession", False),
    (r"\bbecame\s+(?:king|queen|emperor|empress|chancellor|regent|lord|lady)\b",
     "accession", False),
    (r"\bwas\s+founded\b", "founding", True),
    (r"\bfounded\b", "founding", False),
    (r"\bwas\s+(?:invaded|attacked|besieged|sacked)\b", "battle", True),
    (r"\b(?:invaded|attacked|besieged|sacked)\b", "battle", False),
    (r"\b(?:war|battle|siege)\s+(?:broke\s+out|began|ended)\b", "battle", True),
    (r"\bwas\s+betrayed\b", "betrayal", True),
    (r"\b(?:betrayed|deceived)\b", "betrayal", False),
    (r"\b(?:met|encountered)\b", "meeting", False),
    (r"\b(?:travell?ed|sailed|rode|journeyed|fled|returned|arrived)\b", "travel", False),
    (r"\bwas\s+(?:signed|declared|proclaimed)\b", "political", True),
    (r"\b(?:signed|declared|proclaimed|decreed)\b", "political", False),
    (r"\b(?:discovered|uncovered|found)\b", "discovery", False),
]

COMPILED = [(re.compile(p, re.IGNORECASE), kind, passive) for p, kind, passive in TRIGGERS]

#: Prepositions that mark a place rather than a participant.
_PLACE_MARK = re.compile(r"\b(?:in|at|to|from|near|outside|within)\s+$", re.IGNORECASE)
_BY_AGENT = re.compile(r"\bby\s+$", re.IGNORECASE)


class _SpanMatch:
    """Adapts a lemma hit to the `re.Match` interface the role logic expects,
    so both tiers feed the same code path rather than duplicating it."""

    __slots__ = ("_start", "_end", "_text")

    def __init__(self, start, end, text):
        self._start, self._end, self._text = start, end, text

    def start(self):
        return self._start

    def end(self):
        return self._end

    def group(self, *_args):
        return self._text


class Event:
    """One thing that happened.

    `confidence` is honest rather than decorative: 1.0 when the pattern and the
    roles are unambiguous, lower when word order had to be guessed at. Anything
    below `CONFIRM_BELOW` is surfaced to the writer as a question rather than
    written into the graph as fact.
    """

    __slots__ = ("kind", "agent", "patient", "place", "time", "text",
                 "sentence_index", "confidence", "trigger", "factuality")

    def __init__(self, kind, text, sentence_index, agent=None, patient=None,
                 place=None, time=None, confidence=1.0, trigger="",
                 factuality="asserted"):
        self.kind = kind
        self.agent = agent
        self.patient = patient
        self.place = place
        self.time = time
        self.text = text
        self.sentence_index = sentence_index
        self.confidence = confidence
        self.trigger = trigger
        #: Whether the clause actually asserts this — see `factuality.py`.
        #: Only "asserted" events become facts; the rest are surfaced as
        #: questions rather than silently dropped or wrongly believed.
        self.factuality = factuality

    @property
    def is_factual(self):
        return self.factuality == "asserted"

    @property
    def subject(self):
        """Who the event is *about*.

        For a death or birth the patient is the subject when there is one — "the
        death of Aldric" is Aldric's event, even though someone else may have
        caused it.
        """
        if self.kind in ("death", "birth") and self.patient:
            return self.patient
        return self.agent or self.patient

    def describe(self):
        who = self.subject or "?"
        when = self.time.text if self.time else "undated"
        return f"{self.kind}: {who} ({when})"

    def __repr__(self):
        return f"<Event {self.describe()}>"


def extract_events(clause, sentence_index, mentions, time=None, sentence_text=None):
    """Find events in one clause.

    `mentions` is `[(name, start, end, kind), ...]` for this clause, produced by
    `mentions.py` — the entity names the engine already knows about. Grounding
    role assignment in known entities rather than guessing at nouns is what keeps
    this from inventing participants.
    """
    # First matching pattern wins, and only one event comes out of a clause —
    # clauses were already split for exactly this. Order in TRIGGERS matters:
    # "was betrayed" matches both the passive and active patterns, and taking
    # both would emit two events that disagree about who did what to whom.
    matches = []
    for pattern, kind, passive in COMPILED:
        m = pattern.search(clause)
        if m:
            matches.append((m, kind, passive))
            break

    # Second tier: a lemmatiser catches inflections the regex list never
    # enumerated ("was founding", "founds"). Only consulted when the regex tier
    # found nothing, so existing behaviour is unchanged — and only when the
    # clause names someone, since an event with no participants is of no use
    # here anyway and parsing is the expensive step. Returns None when spaCy is
    # unavailable, in which case there is simply no second tier.
    if not matches and mentions:
        from .lemmas import lemma_triggers
        for kind, start, end, passive in (lemma_triggers(clause) or []):
            matches.append((_SpanMatch(start, end, clause[start:end]), kind, passive))

    status = classify_factuality(clause, sentence_text)

    events = []
    for m, kind, passive in matches:

        before = [x for x in mentions if x[2] <= m.start()]
        after = [x for x in mentions if x[1] >= m.end()]

        # A name can contain its own trigger — "the Meridian War began" matches
        # on "War began", so the entity overlaps rather than precedes it. Fall
        # back to an overlapping mention before concluding nobody was named.
        if not before:
            before = [x for x in mentions if x[1] < m.end() and x[2] > m.start()]

        agent = patient = place = None
        confidence = 1.0

        # A place is marked by its preposition regardless of voice — "died AT
        # Ash Harbour" and "was killed AT Dawnhold" are the same construction,
        # and only checking the active branch loses half of them.
        for name, s, _e, _k in after:
            if _PLACE_MARK.search(clause[:s]) and place is None:
                place = name

        if passive:
            # "X was killed (by Y)" / "the death of X" — the named party before
            # the verb is the one it happened to.
            patient = before[-1][0] if before else (after[0][0] if after else None)
            for name, s, _e, _k in after:
                if _BY_AGENT.search(clause[:s]):
                    agent = name
                    break
            if patient is None:
                confidence = 0.4
        else:
            agent = before[-1][0] if before else None
            for name, s, e, mkind in after:
                if name == place:
                    continue
                if patient is None and not _PLACE_MARK.search(clause[:s]):
                    patient = name
            if agent is None:
                # No named party before the verb: the sentence probably relies
                # on a pronoun or an earlier subject. Say so rather than guess.
                confidence = 0.35

        if kind in ("death", "birth") and not passive and patient is None and agent:
            # "Aldric died" — intransitive, so the agent IS the subject.
            patient, agent = agent, None

        events.append(Event(
            kind=kind, text=clause.strip(), sentence_index=sentence_index,
            agent=agent, patient=patient, place=place, time=time,
            confidence=confidence, trigger=m.group(0).strip(),
            factuality=status,
        ))
        break  # one event per clause; clauses were already split for this

    return events
