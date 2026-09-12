"""Typed relationships between characters, read out of the prose.

Phase 4. The Story Atlas app requires every relationship to be entered by hand.
The draft already states most of them.

Three grammatical shapes carry nearly all of it:

* **possessive** — "Aldric's daughter Mara", "the chancellor's brother"
* **appositive** — "Mara Sadel, daughter of Aldric Vane"
* **predicate** — "Mara married Tobin", "Kell served under Locke"

Kinship is worth handling properly because it *inverts*: if Mara is Aldric's
daughter then Aldric is Mara's father, and a graph that stores only one
direction cannot answer half the questions asked of it. The inverse is derived
here rather than left for someone to remember.

Gendered inverses are the one place this declines to guess. "X's parent" from
"X is my child" is safe; choosing *father* over *mother* is not, so it emits the
neutral term rather than inventing a detail the text never gave.
"""

import re

#: relation -> (inverse, symmetric)
KINSHIP = {
    "daughter": ("parent", False),
    "son": ("parent", False),
    "child": ("parent", False),
    "father": ("child", False),
    "mother": ("child", False),
    "parent": ("child", False),
    "brother": ("sibling", True),
    "sister": ("sibling", True),
    "sibling": ("sibling", True),
    "wife": ("spouse", True),
    "husband": ("spouse", True),
    "spouse": ("spouse", True),
    "cousin": ("cousin", True),
    "uncle": ("nibling", False),
    "aunt": ("nibling", False),
    "nephew": ("uncle_or_aunt", False),
    "niece": ("uncle_or_aunt", False),
    "grandfather": ("grandchild", False),
    "grandmother": ("grandchild", False),
    "grandson": ("grandparent", False),
    "granddaughter": ("grandchild", False),
    "heir": ("predecessor", False),
    "successor": ("predecessor", False),
    "predecessor": ("successor", False),
}

#: Non-kin relations stated as a predicate. (pattern, relation, symmetric)
PREDICATES = [
    (r"\bmarried\b|\bwed\b", "spouse", True),
    (r"\bserved\s+under\b", "served_under", False),
    (r"\breported\s+to\b", "reports_to", False),
    (r"\bcommanded\b|\bled\b", "commands", False),
    (r"\bbetrayed\b", "betrayed", False),
    (r"\ballied\s+with\b|\bjoined\s+forces\s+with\b", "allied_with", True),
    (r"\bfought\b|\bfought\s+against\b", "fought", True),
    (r"\btrained\b|\bmentored\b|\btaught\b", "mentored", False),
    (r"\bfounded\b", "founded", False),
    (r"\bmember\s+of\b|\bbelonged\s+to\b|\bjoined\b", "member_of", False),
    (r"\bruled\b|\bgoverned\b", "ruled", False),
]

_COMPILED = [(re.compile(p, re.IGNORECASE), rel, sym) for p, rel, sym in PREDICATES]

_KIN_WORDS = "|".join(sorted(KINSHIP, key=len, reverse=True))
_POSSESSIVE = re.compile(rf"(?P<owner>[A-Z][\w'’-]*(?:\s+[A-Z][\w'’-]*)*)['’]s\s+(?P<rel>{_KIN_WORDS})\b",
                         re.IGNORECASE)
_OF_PHRASE = re.compile(rf"\b(?P<rel>{_KIN_WORDS})\s+of\s+(?P<owner>[A-Z][\w'’-]*(?:\s+[A-Z][\w'’-]*)*)",
                        re.IGNORECASE)


class Relation:
    """One typed relationship, with the sentence that stated it."""

    __slots__ = ("subject", "relation", "target", "sentence_index", "evidence",
                 "confidence", "inferred")

    def __init__(self, subject, relation, target, sentence_index=None,
                 evidence="", confidence=1.0, inferred=False):
        self.subject = subject
        self.relation = relation
        self.target = target
        self.sentence_index = sentence_index
        self.evidence = evidence
        self.confidence = confidence
        self.inferred = inferred

    def key(self):
        return (self.subject, self.relation, self.target)

    def describe(self):
        mark = " (inferred)" if self.inferred else ""
        return f"{self.subject} — {self.relation} → {self.target}{mark}"

    def __repr__(self):
        return f"<Relation {self.describe()}>"


def extract_relations(sentences, index):
    """Find every stated relationship, then add the inverses they imply."""
    found = []

    for sentence in sentences:
        text = sentence.text
        mentions = index.find(text)
        if not mentions:
            continue
        names = [m[0] for m in mentions]

        # "Aldric's daughter Mara" / "Aldric's daughter"
        for m in _POSSESSIVE.finditer(text):
            owner = _resolve(m.group("owner"), index)
            relation = m.group("rel").lower()
            other = _nearest_after(mentions, m.end(), exclude=owner)
            if owner and other:
                found.append(Relation(other, relation + "_of", owner,
                                      sentence.index, text, 1.0))

        # "Mara, daughter of Aldric Vane"
        for m in _OF_PHRASE.finditer(text):
            owner = _resolve(m.group("owner"), index)
            relation = m.group("rel").lower()
            other = _nearest_before(mentions, m.start(), exclude=owner)
            if owner and other:
                found.append(Relation(other, relation + "_of", owner,
                                      sentence.index, text, 1.0))

        # "Mara married Tobin"
        for pattern, relation, _symmetric in _COMPILED:
            hit = pattern.search(text)
            if not hit:
                continue
            before = [n for n, s, e, _k in mentions if e <= hit.start()]
            after = [n for n, s, e, _k in mentions if s >= hit.end()]
            if before and after and before[-1] != after[0]:
                found.append(Relation(before[-1], relation, after[0],
                                      sentence.index, text, 0.9))

    return _add_inverses(_dedupe(found))


def _resolve(raw, index):
    """Map a matched surface name onto a known entity, or `None`."""
    hits = index.find(raw)
    return hits[0][0] if hits else None


def _nearest_after(mentions, position, exclude=None):
    for name, start, _end, _kind in mentions:
        if start >= position and name != exclude:
            return name
    return None


def _nearest_before(mentions, position, exclude=None):
    for name, _start, end, _kind in reversed(mentions):
        if end <= position and name != exclude:
            return name
    return None


def _dedupe(relations):
    seen, out = set(), []
    for r in relations:
        if r.key() in seen or r.subject == r.target:
            continue
        seen.add(r.key())
        out.append(r)
    return out


def _add_inverses(relations):
    """Derive the reverse of every kinship relation.

    A graph storing only "Mara is Aldric's daughter" cannot answer "who are
    Aldric's children", which is the same fact asked the other way round.
    """
    known = {r.key() for r in relations}
    out = list(relations)

    for r in relations:
        base = r.relation[:-3] if r.relation.endswith("_of") else r.relation
        entry = KINSHIP.get(base)
        if entry is None:
            for _p, rel, symmetric in PREDICATES:
                if rel == r.relation and symmetric:
                    entry = (rel, True)
                    break
        if entry is None:
            continue

        inverse, symmetric = entry
        relation = r.relation if symmetric else (
            inverse + "_of" if r.relation.endswith("_of") else inverse)
        key = (r.target, relation, r.subject)
        if key in known:
            continue
        known.add(key)
        out.append(Relation(r.target, relation, r.subject, r.sentence_index,
                            r.evidence, round(r.confidence * 0.95, 4), inferred=True))
    return out
