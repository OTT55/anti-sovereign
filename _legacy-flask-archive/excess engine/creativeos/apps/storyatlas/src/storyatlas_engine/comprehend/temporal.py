"""Reading time out of prose, as constraints rather than answers.

A draft almost never states every date. It states a few, and then relates
everything else to them: *"Three years later…"*, *"that same winter"*, *"long
before the siege"*. The existing Story Atlas detects those phrases and then
throws them away, storing `year: None` — which is why its timeline cannot order
anything it was not handed a literal number for.

The fix is to stop treating a time expression as a *value* and start treating it
as a **constraint**. "Three years later" is not an unknown date; it is the
equation `this = previous + 3`. Collect all of them and the dates that were never
written down can be *solved for*. That is `solver.py`'s job; this module's job is
to read the equations off the page.
"""

import re

#: Written-out numbers, which fiction uses far more than digits.
NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
    "a": 1, "an": 1, "several": 3, "a few": 3, "a couple of": 2, "many": 5,
}

#: How many years a unit is worth. Sub-year units collapse to 0 — within a year
#: for dating purposes, but still ordered, which is what actually matters.
UNIT_YEARS = {
    "year": 1, "years": 1, "winter": 1, "winters": 1, "summer": 1, "summers": 1,
    "decade": 10, "decades": 10, "century": 100, "centuries": 100,
    "generation": 25, "generations": 25,
    "month": 0, "months": 0, "week": 0, "weeks": 0, "day": 0, "days": 0,
    "night": 0, "nights": 0, "hour": 0, "hours": 0,
}

_NUM = r"(?:\d+|" + "|".join(sorted(NUMBER_WORDS, key=len, reverse=True)) + r")"
_UNIT = r"(?:" + "|".join(sorted(UNIT_YEARS, key=len, reverse=True)) + r")"


class TimeRef:
    """One time expression found in the text, as a constraint on an event.

    `kind` is one of:
      * `absolute` — a stated year. `value` is that year.
      * `offset`   — `value` years after (positive) or before (negative) whatever
                     the narrative was last anchored to.
      * `same`     — the same moment as the previous anchor.
      * `before` / `after` — ordered against the previous anchor, distance unknown.
      * `age`      — `value` years after the subject's own birth.
    """

    __slots__ = ("kind", "value", "text", "unit", "secondary")

    def __init__(self, kind, value, text, unit=None, secondary=None):
        self.kind = kind
        self.value = value
        self.text = text
        self.unit = unit
        #: A weaker time expression found in the same clause. Kept rather than
        #: discarded so the two can be checked against each other: "three years
        #: later ... in the year 1150" states a date AND a relation, and if they
        #: disagree that is a continuity error worth reporting.
        self.secondary = secondary

    def __repr__(self):
        return f"<TimeRef {self.kind} {self.value} {self.text!r}>"

    def __eq__(self, other):
        return (isinstance(other, TimeRef) and self.kind == other.kind
                and self.value == other.value)


def parse_number(token):
    """`"three"` and `"3"` both mean 3."""
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    if token in NUMBER_WORDS:
        return NUMBER_WORDS[token]
    total, found = 0, False
    for word in token.split():
        if word in NUMBER_WORDS:
            total += NUMBER_WORDS[word]
            found = True
    return total if found else None


def year_pattern(era_label="Year"):
    """Absolute dates, including a space's own calendar.

    A world's dates rarely look like ours — "1147 AR", "Year 44", "in the third
    age". `era_label` lets a space name its own era so its own dates are
    recognised rather than ignored.
    """
    era = re.escape(era_label)
    return re.compile(
        r"(?:"
        rf"\bin\s+the\s+year\s+(?P<y1>\d{{1,5}})"
        rf"|\b{era}\s+(?P<y2>\d{{1,5}})"
        rf"|\b(?P<y3>\d{{3,5}})\s*(?:AR|BR|AD|BC|CE|BCE|A\.R\.)\b"
        rf"|\bin\s+(?P<y4>\d{{3,5}})\b"
        r")",
        re.IGNORECASE,
    )


_OFFSET_RE = re.compile(
    rf"\b(?P<num>{_NUM}(?:\s+{_NUM})?)\s+(?P<unit>{_UNIT})\s+"
    r"(?P<dir>later|afterwards?|after|earlier|before|previously|ago|on)\b",
    re.IGNORECASE,
)
_SAME_RE = re.compile(
    r"\b(?:that\s+(?:same\s+)?(?:year|winter|summer|day|night|month)"
    r"|the\s+same\s+(?:year|winter|summer|day|night|month)"
    r"|at\s+the\s+same\s+time|meanwhile|simultaneously)\b",
    re.IGNORECASE,
)
_AFTER_RE = re.compile(
    r"\b(?:then|afterwards?|subsequently|later|soon\s+after|shortly\s+after"
    r"|in\s+the\s+years\s+that\s+followed|thereafter)\b", re.IGNORECASE)
_BEFORE_RE = re.compile(
    r"\b(?:earlier|previously|before\s+that|long\s+before|beforehand)\b", re.IGNORECASE)
_AGE_RE = re.compile(
    rf"\bat\s+the\s+age\s+of\s+(?P<num>{_NUM})|\baged\s+(?P<num2>{_NUM})\b", re.IGNORECASE)


def _relative_only(text):
    """The offset or "same year" in a clause, ignoring any stated year.

    Used to keep a relation alongside an absolute date so the two can be
    cross-checked rather than one silently winning.
    """
    m = _OFFSET_RE.search(text)
    if m:
        n = parse_number(m.group("num"))
        if n is not None:
            unit = m.group("unit").lower()
            direction = m.group("dir").lower()
            years = n * UNIT_YEARS.get(unit, 1)
            backwards = direction in ("earlier", "before", "previously", "ago")
            return TimeRef("offset", -years if backwards else years, m.group(0), unit)
    m = _SAME_RE.search(text)
    if m:
        return TimeRef("same", 0, m.group(0))
    return None


def extract_time(text, era_label="Year"):
    """Find the time constraint a clause carries, or `None`.

    Ordered by how much each form actually pins down: an explicit year beats an
    offset, an offset beats "that same year", and a bare "then" is the weakest.
    Taking the strongest available means a sentence carrying both a year and a
    "later" is anchored by the year rather than left floating.
    """
    m = year_pattern(era_label).search(text)
    if m:
        value = next((int(g) for g in m.groups() if g and g.isdigit()), None)
        if value is not None:
            return TimeRef("absolute", value, m.group(0),
                           secondary=_relative_only(text))

    m = _AGE_RE.search(text)
    if m:
        raw = m.group("num") or m.group("num2")
        n = parse_number(raw)
        if n is not None:
            return TimeRef("age", n, m.group(0))

    m = _OFFSET_RE.search(text)
    if m:
        n = parse_number(m.group("num"))
        unit = m.group("unit").lower()
        direction = m.group("dir").lower()
        if n is not None:
            years = n * UNIT_YEARS.get(unit, 1)
            backwards = direction in ("earlier", "before", "previously", "ago")
            return TimeRef("offset", -years if backwards else years, m.group(0), unit)

    m = _SAME_RE.search(text)
    if m:
        return TimeRef("same", 0, m.group(0))

    m = _BEFORE_RE.search(text)
    if m:
        return TimeRef("before", None, m.group(0))

    m = _AFTER_RE.search(text)
    if m:
        return TimeRef("after", None, m.group(0))

    return None
