"""Finding where known entities are named, including when they are named loosely.

Prose refers to one person many ways: "Chancellor Aldric Vane" once, then
"Aldric", then "Vane", then "he". A system that treats those as four different
things cannot group anything, which is the failure this whole engine exists to
fix.

Two mechanisms, both deterministic:

* **Alias matching** — a known entity's full name generates the short forms a
  writer will actually use, so "Aldric" resolves to the same entity as
  "Aldric Vane".
* **Pronoun carry-over** — "He died three years later" attaches to the most
  recent compatible subject. Strictly bounded: only the immediately preceding
  sentence, and only when exactly one candidate fits. Guessing further than that
  produces confident nonsense, so where it cannot tell, it declines and the
  event's confidence drops instead.
"""

import re

_TITLES = {
    "mr", "mrs", "ms", "dr", "st", "lord", "lady", "king", "queen", "prince",
    "princess", "chancellor", "admiral", "captain", "general", "commander",
    "sir", "dame", "emperor", "empress", "regent", "duke", "duchess", "father",
    "mother", "sister", "brother", "master", "professor", "colonel", "sergeant",
}

_MALE = {"he", "him", "his"}
_FEMALE = {"she", "her", "hers"}
_NEUTRAL = {"they", "them", "their"}
PRONOUNS = _MALE | _FEMALE | _NEUTRAL

_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")


#: Connectives that appear inside names ("Order **of the** Broken Crown") but
#: must never become aliases on their own. Without this guard "of" is a valid
#: short form of "Order of the Broken Crown", and it then matches "the age of
#: thirty" — which silently misattributes an event and corrupts every date
#: computed from it.
_CONNECTIVES = {"of", "the", "de", "la", "le", "van", "von", "del", "and", "a", "an"}

#: Head nouns that mark a name as a *thing* rather than a person. A person
#: shortens by first or last name ("Aldric Vane" → "Aldric"); a named thing
#: shortens by its head noun ("the Accord", "the Order"), never by the proper
#: noun in front of it. Without this, "Dawnhold Accord" claims "Dawnhold" and
#: swallows the city it was named after.
_THING_HEADS = {
    "accord", "treaty", "pact", "war", "battle", "siege", "rebellion",
    "uprising", "revolution", "massacre", "plague", "crusade", "campaign",
    "order", "house", "guild", "company", "council", "senate", "assembly",
    "conclave", "circle", "brotherhood", "sisterhood", "legion", "corps",
    "alliance", "league", "federation", "ministry", "bureau", "academy",
}


def aliases_for(name):
    """The short forms a writer will plausibly use for this name.

    "Chancellor Aldric Vane" → {"chancellor aldric vane", "aldric vane",
    "aldric", "vane"}. Single-word names generate only themselves — inventing
    aliases for them would collide constantly.
    """
    forms = {name.lower()}
    words = name.split()

    stripped = [w for w in words if w.lower().strip(".") not in _TITLES]
    if stripped and len(stripped) < len(words):
        forms.add(" ".join(stripped).lower())

    if len(stripped) >= 2:
        head, tail = stripped[0].lower(), stripped[-1].lower()
        # A named *thing* shortens by its head noun only. "Dawnhold Accord" is
        # "the Accord", never "Dawnhold" — that is the city it was named after,
        # and claiming it merges two distinct entities into one.
        if tail in _THING_HEADS:
            forms.add(tail)
        else:
            # A person shortens either way: first name or surname.
            if head not in _CONNECTIVES:
                forms.add(head)
            if tail not in _CONNECTIVES:
                forms.add(tail)
    return {f for f in forms if len(f) > 1 and f not in _CONNECTIVES}


class MentionIndex:
    """Resolves surface strings to canonical entity names."""

    def __init__(self, names):
        self.names = list(names)
        self.by_alias = {}
        # Longer names claim their aliases first, so an ambiguous short form
        # ("Aldric") belongs to whoever introduced it, not to whoever is last.
        for name in sorted(self.names, key=lambda n: -len(n)):
            for alias in aliases_for(name):
                self.by_alias.setdefault(alias, name)
        self._alias_re = self._build_regex()

    def _build_regex(self):
        if not self.by_alias:
            return None
        alts = sorted(self.by_alias, key=len, reverse=True)
        return re.compile(r"\b(" + "|".join(re.escape(a) for a in alts) + r")\b",
                          re.IGNORECASE)

    def find(self, text):
        """`[(canonical_name, start, end, "entity"), ...]`, non-overlapping."""
        if self._alias_re is None:
            return []
        found, taken = [], []
        for m in self._alias_re.finditer(text):
            span = m.span(1)
            if any(s <= span[0] < e for s, e in taken):
                continue
            canonical = self.by_alias.get(m.group(1).lower())
            if canonical:
                found.append((canonical, span[0], span[1], "entity"))
                taken.append(span)
        return sorted(found, key=lambda x: x[1])

    def find_pronouns(self, text):
        return [(m.group(0).lower(), m.start(), m.end())
                for m in _WORD.finditer(text) if m.group(0).lower() in PRONOUNS]


_SENTENCE_START = re.compile(r"(?:^|[.!?]\s+|\n)\s*$")
#: A capitalised run, allowing lowercase connectives *between* capitals so
#: "Order of the Broken Crown" stays one name instead of fragmenting into
#: "Order of" and "Broken Crown".
#: "and" is deliberately NOT a connective here. "Order of the Broken Crown" is
#: one name, but "Aldric Vane and Mara Sadel" is two — and the second shape is
#: far more common in prose. Allowing "and" made that a single entity called
#: "Aldric Vane and Mara Sadel", which then matched nothing and lost both
#: characters. A name genuinely containing "and" is rare enough to lose.
_CAP_RUN = re.compile(
    r"\b([A-Z][a-z'’-]+(?:\s+(?:(?:of|the|de|la|le|van|von|del)\s+)*[A-Z][a-z'’-]+)*)"
)
_SPEECH = re.compile(r'["“”]')

#: Words that begin sentences constantly and are not names.
_NOT_NAMES = {
    "the", "a", "an", "and", "but", "then", "when", "where", "what", "who",
    "he", "she", "they", "it", "his", "her", "their", "this", "that", "these",
    "those", "there", "here", "in", "on", "at", "to", "from", "by", "for",
    "with", "after", "before", "during", "years", "year", "later", "meanwhile",
    "many", "most", "some", "no", "not", "if", "as", "so", "yet", "still",
    "three", "two", "one", "four", "five", "within", "outside", "across",
}


def discover_names(text, min_repeats=2):
    """Find likely entity names in a draft with no prior knowledge.

    Two signals, both cheap and both reliable: a multi-word capitalised phrase
    is trustworthy even once (few things but names look like "Aldric Vane"), and
    a single capitalised word needs repetition before it is believed, because
    every sentence starts with a capital.

    Names introduced by a title ("Chancellor Aldric") are kept whole so the
    alias machinery can strip the title itself.
    """
    counts = {}
    for m in _CAP_RUN.finditer(text):
        phrase = m.group(1).strip()
        words = phrase.split()
        # Drop a leading sentence-start capital that is only grammar.
        if words and words[0].lower() in _NOT_NAMES:
            words = words[1:]
        if not words:
            continue
        # A run that is only a title is not a name.
        if all(w.lower().strip(".") in _TITLES for w in words):
            continue
        # "Aldric Vane's daughter" must not register the owner as "Aldric
        # Vane's" — the possessive is grammar, not part of the name, and an
        # entity stored with it never matches its own plain mentions.
        words = [re.sub(r"['’]s$", "", w) for w in words]
        phrase = " ".join(w for w in words if w)
        if len(phrase) < 2 or phrase.lower() in _NOT_NAMES:
            continue
        at_start = bool(_SENTENCE_START.search(text[:m.start(1)][-3:]))
        entry = counts.setdefault(phrase, {"count": 0, "mid_sentence": 0})
        entry["count"] += 1
        if not at_start:
            entry["mid_sentence"] += 1

    names = []
    for phrase, info in counts.items():
        multi_word = len(phrase.split()) > 1
        if multi_word or info["count"] >= min_repeats or info["mid_sentence"] >= 1:
            names.append(phrase)

    # Prefer the fullest form: "Aldric Vane" absorbs a bare "Aldric".
    names.sort(key=lambda n: (-len(n.split()), -counts[n]["count"]))
    kept = []
    for name in names:
        parts = set(aliases_for(name))
        if any(parts & set(aliases_for(k)) for k in kept):
            continue
        kept.append(name)
    return kept


def resolve_pronoun_subject(clause, previous_subjects, is_person=None):
    """Who "he"/"she"/"they" refers to, or `None` when it genuinely cannot tell.

    Only considers the single most recent subject. Deliberately conservative:
    a wrong antecedent silently attributes a death to the wrong character, which
    is far worse than admitting uncertainty and asking.

    `is_person(name) -> bool` filters antecedents by what they are. Without it,
    *"Dawnhold was founded in 1090. He was crowned at the age of thirty."*
    resolves "he" to a castle, because the castle is simply the nearest thing
    mentioned. The damage is not the odd attribution itself — it is that the
    coronation then has no birth year to count thirty from, so it never gets
    dated, so the next sentence's "three years later" anchors to the *founding*
    instead, and a death lands four decades early. One misattributed pronoun
    silently re-dates everything downstream of it, which is why proximity alone
    is not a good enough rule.
    """
    words = [w.lower() for w in _WORD.findall(clause[:40])]
    if not any(w in PRONOUNS for w in words):
        return None
    if len(previous_subjects) != 1:
        return None
    candidate = previous_subjects[-1]
    if is_person is not None and not is_person(candidate):
        return None
    return candidate
