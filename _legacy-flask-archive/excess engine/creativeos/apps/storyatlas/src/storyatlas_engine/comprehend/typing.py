"""Deciding *what kind of thing* each name is.

Phase 1 found names but treated them all alike, so "Order of the Broken Crown"
could turn up in a per-person grouping. A timeline that cannot tell a person
from a place from a war cannot group properly, and grouping is the point.

No model. Each candidate type accumulates **evidence** from how the prose
actually uses the name, and the strongest wins. Where two types tie, the engine
declines and asks — same discipline as everywhere else: being visibly unsure
beats being confidently wrong.

The evidence is deliberately about *usage*, not vocabulary lists, so it works on
invented words. "Ravenmoor" is a place because the text says "fled to
Ravenmoor", not because a gazetteer has heard of it.
"""

import re
from collections import defaultdict

CHARACTER = "character"
LOCATION = "location"
ORGANIZATION = "organization"
EVENT = "event"
UNKNOWN = "other"

#: Titles that mark a person outright.
_PERSON_TITLES = {
    "mr", "mrs", "ms", "dr", "lord", "lady", "king", "queen", "prince",
    "princess", "chancellor", "admiral", "captain", "general", "commander",
    "sir", "dame", "emperor", "empress", "regent", "duke", "duchess",
    "professor", "colonel", "sergeant", "baron", "count", "countess",
}

#: Head nouns that mark an organisation.
_ORG_WORDS = {
    "order", "house", "guild", "company", "council", "senate", "assembly",
    "conclave", "circle", "brotherhood", "sisterhood", "legion", "corps",
    "syndicate", "consortium", "alliance", "league", "federation", "ministry",
    "bureau", "academy", "school", "church", "temple", "clan", "tribe",
}

#: Head nouns that mark an event.
_EVENT_WORDS = {
    "war", "battle", "siege", "accord", "treaty", "pact", "rebellion",
    "uprising", "revolution", "massacre", "plague", "famine", "crusade",
    "campaign", "conference", "summit", "trial", "coronation",
}

#: Head nouns that mark a place.
_PLACE_WORDS = {
    "city", "town", "village", "keep", "castle", "fortress", "harbour",
    "harbor", "port", "valley", "mountain", "river", "forest", "isle",
    "island", "province", "kingdom", "empire", "realm", "region", "hold",
    "moor", "reach", "bay", "coast", "gate", "bridge", "road", "tower",
}

#: Verbs only a person does.
_PERSON_VERBS = re.compile(
    r"\b(?:said|says|spoke|replied|asked|whispered|shouted|thought|smiled|"
    r"laughed|wept|nodded|walked|ran|rode|sailed|drew|struck|married|wed|"
    r"was\s+born|died|killed|slew|betrayed|loved|feared|knew)\b", re.IGNORECASE)

#: Verbs whose subject is an organisation or an event, not a person.
_ORG_VERBS = re.compile(
    r"\b(?:was\s+founded|disbanded|convened|ruled|governed|controlled)\b", re.IGNORECASE)
_EVENT_VERBS = re.compile(
    r"\b(?:broke\s+out|began|ended|raged|erupted|concluded)\b", re.IGNORECASE)

_PLACE_PREP = re.compile(r"\b(?:in|at|to|from|near|outside|within|toward|towards|into)\s+$",
                         re.IGNORECASE)
_OF_PLACE = re.compile(r"\b(?:city|town|port|keep|castle|isle|province)\s+of\s+$", re.IGNORECASE)

#: Words that follow a name without it being the subject of a verb.
_NOT_A_VERB = {
    "and", "or", "but", "of", "the", "a", "an", "in", "at", "to", "from",
    "for", "with", "by", "on", "as", "than", "then", "that", "which", "who",
    "whose", "when", "where", "while", "is", "was", "were", "are", "be",
}

#: A name followed by a lowercase word that is not a preposition or connective
#: is in subject position doing something — and only people act. Far more
#: general than a whitelist of verbs, which is whack-a-mole: "waited" and
#: "watched" are as person-ish as "spoke", and no list ever contains them all.
_ACTING = re.compile(r"^\s+(?P<word>[a-z][a-z'’-]+)")


class TypeVerdict:
    """A decision about one name, with the evidence that produced it."""

    __slots__ = ("name", "kind", "scores", "confident", "runner_up")

    def __init__(self, name, kind, scores, confident, runner_up=None):
        self.name = name
        self.kind = kind
        self.scores = scores
        self.confident = confident
        self.runner_up = runner_up

    def describe(self):
        mark = "" if self.confident else " (uncertain)"
        return f"{self.name}: {self.kind}{mark}"

    def __repr__(self):
        return f"<TypeVerdict {self.describe()}>"


def _head_word(name):
    words = [w.lower().strip(".,") for w in name.split()]
    if not words:
        return ""
    # "Order of the Broken Crown" — the head is the first word, not the last.
    for w in words:
        if w in _ORG_WORDS or w in _EVENT_WORDS or w in _PLACE_WORDS:
            return w
    return words[-1]


#: Events whose subject must be a person.
_PERSONAL_EVENTS = {"birth", "death", "marriage", "accession", "betrayal"}


def classify(names, text, mention_index, events=None):
    """Type every name from how the text uses it.

    Returns `{name: TypeVerdict}`. Pure: same text and names in, same verdicts
    out.

    `events` is the strongest evidence available and costs nothing extra, since
    extraction already worked out the roles: whoever *acts* is a person, whoever
    is born or dies is a person, and whatever a preposition marks as the setting
    is a place. Regex over surface text is the fallback, not the primary signal.
    """
    scores = {name: defaultdict(float) for name in names}

    for event in events or []:
        if event.confidence < 0.5:
            continue
        # Only people act.
        if event.agent in scores:
            scores[event.agent][CHARACTER] += 2.0
        # Only people are born, die, marry, or take a throne.
        if event.patient in scores and event.kind in _PERSONAL_EVENTS:
            scores[event.patient][CHARACTER] += 2.0
        # A founding's object is the thing founded.
        if event.kind == "founding" and event.patient in scores:
            scores[event.patient][ORGANIZATION] += 2.0
        # A preposition already marked this as the setting.
        if event.place in scores:
            scores[event.place][LOCATION] += 2.5

    for name in names:
        words = [w.lower().strip(".") for w in name.split()]
        head = _head_word(name)

        # Structural evidence from the name itself.
        if any(w in _PERSON_TITLES for w in words):
            scores[name][CHARACTER] += 3.0
        if head in _ORG_WORDS:
            scores[name][ORGANIZATION] += 3.0
        if head in _EVENT_WORDS:
            scores[name][EVENT] += 3.0
        if head in _PLACE_WORDS:
            scores[name][LOCATION] += 2.5
        # "X of Y" reads as an organisation or a title, rarely a bare person.
        if " of " in name.lower() and head not in _PLACE_WORDS:
            scores[name][ORGANIZATION] += 1.0

    # Usage evidence, one mention at a time.
    for name, start, end, _kind in mention_index.find(text):
        before = text[max(0, start - 40):start]
        after = text[end:end + 60]

        if _OF_PLACE.search(before):
            scores[name][LOCATION] += 3.0
        elif _PLACE_PREP.search(before):
            scores[name][LOCATION] += 1.0

        head_of_clause = after.lstrip()
        if _PERSON_VERBS.match(head_of_clause) or _PERSON_VERBS.search(after[:30]):
            scores[name][CHARACTER] += 1.5

        acting = _ACTING.match(after)
        if acting and acting.group("word").lower() not in _NOT_A_VERB:
            scores[name][CHARACTER] += 2.0
        if _ORG_VERBS.search(after[:40]):
            scores[name][ORGANIZATION] += 2.0
        if _EVENT_VERBS.search(after[:40]):
            scores[name][EVENT] += 2.0

        # Possessive of a person: "Aldric's daughter".
        if after.startswith("'s") or after.startswith("’s"):
            scores[name][CHARACTER] += 0.5

    verdicts = {}
    for name in names:
        table = scores[name]
        if not table:
            verdicts[name] = TypeVerdict(name, UNKNOWN, {}, confident=False)
            continue
        ranked = sorted(table.items(), key=lambda kv: -kv[1])
        best_kind, best_score = ranked[0]
        second = ranked[1] if len(ranked) > 1 else (None, 0.0)
        # Confident when the leader is clear of the runner-up. A narrow win means
        # the evidence genuinely points both ways, which is a question, not a fact.
        confident = best_score >= 1.5 and (best_score - second[1]) >= 1.0
        verdicts[name] = TypeVerdict(
            name, best_kind if confident else UNKNOWN, dict(table),
            confident=confident, runner_up=second[0] if second[1] > 0 else None,
        )
    return verdicts


def people(verdicts):
    return [v.name for v in verdicts.values() if v.kind == CHARACTER]


def places(verdicts):
    return [v.name for v in verdicts.values() if v.kind == LOCATION]


def organizations(verdicts):
    return [v.name for v in verdicts.values() if v.kind == ORGANIZATION]


def events(verdicts):
    return [v.name for v in verdicts.values() if v.kind == EVENT]
