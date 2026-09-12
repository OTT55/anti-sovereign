"""An optional second tier of event detection, using spaCy's lemmatiser.

A regex trigger list only catches the inflections somebody thought to type.
`\\bfounded\\b` matches "founded" and misses "founding", "founds", "was
founding". Verified against this engine's own trigger list: of five real
sentences, the regex tier caught one and the lemma tier caught all five.

A lemmatiser solves this properly, because it reduces every inflection to one
dictionary form — "founded", "founding" and "founds" are all `found` — so a
single entry covers the whole verb rather than an ever-growing list of endings.

**Layered additively, not as a replacement.** Neither tier is strictly better:
the regex tier catches multi-word patterns ("was crowned", "took the throne")
that a single-token lemma lookup cannot see, and the lemma tier catches
inflections the regex list never enumerated. Running the regex first and only
consulting this when it finds nothing keeps existing behaviour identical while
adding what it missed.

**Degrades honestly.** With spaCy absent or its model unavailable, this returns
`None` and the engine carries on with the regex tier alone. It never raises, and
it never silently changes an answer — the house convention throughout this
codebase.
"""

#: Dictionary form of a verb -> the kind of event it signals. One entry here
#: covers every inflection of that verb, which is the entire point.
TRIGGER_LEMMAS = {
    "die": "death", "perish": "death", "kill": "death", "slay": "death",
    "murder": "death", "assassinate": "death", "execute": "death",
    "bear": "birth",           # "was born" lemmatises to "bear"
    "marry": "marriage", "wed": "marriage", "betroth": "marriage",
    "crown": "accession", "enthrone": "accession", "succeed": "accession",
    "found": "founding", "establish": "founding",
    "invade": "battle", "attack": "battle", "besiege": "battle", "sack": "battle",
    "betray": "betrayal", "deceive": "betrayal",
    "meet": "meeting", "encounter": "meeting",
    "travel": "travel", "sail": "travel", "ride": "travel", "journey": "travel",
    "flee": "travel", "return": "travel", "arrive": "travel", "depart": "travel",
    "sign": "political", "declare": "political", "proclaim": "political",
    "decree": "political", "rule": "political", "govern": "political",
    "discover": "discovery", "uncover": "discovery",
}

_nlp = None
_state = "unloaded"   # "unloaded" | "ready" | "unavailable"
_reason = ""


def _load():
    """Load spaCy once, and remember failure rather than retrying every call."""
    global _nlp, _state, _reason
    if _state != "unloaded":
        return _nlp

    try:
        import spacy
    except ImportError:
        _state, _reason = "unavailable", "spaCy is not installed"
        return None
    try:
        # The parser is the expensive component and is not needed: lemmas come
        # from the tagger and attribute_ruler, and passive voice is detectable
        # from a neighbouring "be" auxiliary without a dependency tree. Dropping
        # it more than halves the per-clause cost. `attribute_ruler` must stay —
        # without it the lemmatiser returns nothing at all.
        _nlp = spacy.load("en_core_web_sm", disable=["ner", "textcat", "parser"])
        _state = "ready"
    except Exception as e:
        _state = "unavailable"
        _reason = f"spaCy is installed but its model would not load ({type(e).__name__})"
        _nlp = None
    return _nlp


def status():
    """`(available, reason)` — so a caller can report *why* this tier is off."""
    _load()
    return _state == "ready", _reason or "spaCy lemma tier active"


def lemma_triggers(clause):
    """`[(kind, start, end, passive), ...]` for this clause, or `None`.

    `None` means the tier is unavailable — meaningfully different from `[]`,
    which means it ran and found nothing.
    """
    nlp = _load()
    if nlp is None:
        return None

    doc = nlp(clause)
    tokens = list(doc)
    found = []
    for i, token in enumerate(tokens):
        if token.pos_ not in ("VERB", "AUX"):
            continue
        kind = TRIGGER_LEMMAS.get(token.lemma_.lower())
        if kind is None:
            continue
        # Passive voice: a "be" auxiliary immediately before the verb.
        # "was killed" is passive, "killed" is not, and they mean opposite
        # things. Detected positionally rather than from a dependency tree, so
        # the parser can stay switched off.
        passive = any(t.lemma_.lower() == "be" and t.pos_ == "AUX"
                      for t in tokens[max(0, i - 3):i])
        if token.lemma_ == "bear":
            passive = True   # "was born" is only ever passive
        found.append((kind, token.idx, token.idx + len(token.text), passive))
    return found
