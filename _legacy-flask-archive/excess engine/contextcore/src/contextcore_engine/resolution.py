"""Phase 3 — entity resolution and a maintained ontology.

The constitution names this gap directly: *"resolve duplicate entities"* and
*"maintain canonical definitions."* Today's dedup is exact string equality, so
**"Acme Corp"** and **"Acme Corporation"** are two entities that never meet,
and every question about either sees half the facts.

Two deterministic mechanisms, no model:

* **Resolution** — normalise, then fuzzy-match. Two names resolve to one entity
  when they are close enough *and* their types agree.
* **An ontology** — canonical name, its known aliases, and a registry of entity
  types, so the vocabulary is maintained rather than accumulated ad hoc.

The threshold is deliberately conservative. Merging two entities that are
genuinely different is far worse than leaving two records for one thing: a
wrong merge silently attributes one company's contracts to another, and nothing
downstream can detect it. A missed merge is visible and a human can fix it.
"""

import re
from collections import defaultdict

#: Legal-form and honorific suffixes that carry no identity. "Acme Corp" and
#: "Acme Corporation" differ only by one of these.
_NOISE_TOKENS = {
    "inc", "inc.", "incorporated", "corp", "corp.", "corporation", "co", "co.",
    "company", "ltd", "ltd.", "limited", "llc", "llp", "plc", "gmbh", "sa",
    "ag", "nv", "bv", "pty", "group", "holdings", "holding", "international",
    "the", "a", "an", "and", "&",
}

#: Types that may merge with each other. An organisation and a person sharing a
#: name are two things, not one — a rule that costs nothing and prevents the
#: worst class of wrong merge.
_COMPATIBLE = {
    ("organization", "organization"), ("person", "person"),
    ("place", "place"), ("product", "product"), ("concept", "concept"),
    ("date", "date"), ("event", "event"),
}

#: Above this, two names of compatible type are the same entity.
MERGE_THRESHOLD = 0.85


def normalize(name):
    """Strip case, punctuation and legal-form noise down to identity tokens."""
    lowered = re.sub(r"[^\w\s&]", " ", (name or "").lower())
    tokens = [t for t in lowered.split() if t and t not in _NOISE_TOKENS]
    return " ".join(tokens)


def _bigrams(text):
    padded = f" {text} "
    return {padded[i:i + 2] for i in range(len(padded) - 1)}


def _numbers(text):
    """Digit sequences in a name. These carry identity, not spelling."""
    return tuple(re.findall(r"\d+", text or ""))


def name_similarity(left, right):
    """0.0–1.0 similarity of two names after normalisation.

    Exact normalised equality short-circuits to 1.0 — "Acme Corp" and "Acme
    Corporation" both normalise to "acme", which is the whole point. Otherwise
    a character-bigram Dice coefficient, which handles typos and word order
    ("Vane, Aldric" vs "Aldric Vane") better than prefix matching.

    **Numbers veto.** Bigram similarity is near-blind to digits: "Invoice 4471"
    and "Invoice 4472" share every bigram but two and score ~0.97, so a corpus
    of numbered documents collapses into a single entity — measured once as 800
    distinct organisations resolving to one cluster. A differing number is a
    difference in *identity*, not in spelling, so it refuses the match outright
    rather than being outvoted by the letters around it.
    """
    a, b = normalize(left), normalize(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    left_numbers, right_numbers = _numbers(a), _numbers(b)
    if left_numbers != right_numbers:
        # One name numbered and the other not ("Acme" vs "Acme 2") is also a
        # distinction worth keeping — the same rule covers it.
        return 0.0

    ga, gb = _bigrams(a), _bigrams(b)
    if not ga or not gb:
        return 0.0
    return 2 * len(ga & gb) / (len(ga) + len(gb))


def types_compatible(left_type, right_type):
    left = (left_type or "concept").lower()
    right = (right_type or "concept").lower()
    if left == right:
        return True
    return (left, right) in _COMPATIBLE or (right, left) in _COMPATIBLE


class Cluster:
    """One resolved entity: a canonical name plus everything that meant it."""

    __slots__ = ("canonical", "kind", "aliases", "members")

    def __init__(self, canonical, kind, members):
        self.canonical = canonical
        self.kind = kind
        self.members = members            # every (name, type) seen
        self.aliases = sorted({n for n, _t in members if n != canonical})

    def describe(self):
        extra = f" (also: {', '.join(self.aliases)})" if self.aliases else ""
        return f"{self.canonical} [{self.kind}]{extra}"

    def __repr__(self):
        return f"<Cluster {self.describe()}>"


def _blocking_keys(name):
    """Cheap keys that any two matching names must share at least one of.

    Comparing every name against every cluster is quadratic — 1.66s for 800
    distinct entities, and four times that for each doubling. Blocking is the
    standard fix: only names sharing a key are ever compared.

    The key pairs the name's numbers (which now veto a match outright) with the
    **first letter of each token**, indexed so any single shared initial is
    enough. Using the whole set of initials as one key would be faster still
    and would break "Vane, Aldric" against "Aldric Vane", which is precisely
    the reordering this is supposed to catch — recall matters more than the
    extra comparisons.
    """
    normalised = normalize(name)
    numbers = _numbers(normalised)
    initials = {token[0] for token in normalised.split() if token} or {""}
    return [(numbers, initial) for initial in initials]


def resolve(entities, threshold=MERGE_THRESHOLD):
    """Group raw extracted entities into resolved clusters.

    `entities` is `[{"name", "type"}, ...]` as extraction produces them.

    The canonical name is the **longest** surface form, not the most frequent:
    "Acme Corporation" is more useful as the display name than "Acme", and the
    fuller form is the one a reader can disambiguate.
    """
    clusters = []
    index = defaultdict(list)   # blocking key -> cluster positions

    for entity in entities:
        name = (entity.get("name") or "").strip()
        kind = (entity.get("type") or "concept").strip().lower()
        if not name:
            continue

        keys = _blocking_keys(name)
        candidates = {position for key in keys for position in index[key]}

        placed = False
        for position in sorted(candidates):
            cluster = clusters[position]
            if not types_compatible(kind, cluster["kind"]):
                continue
            if any(name_similarity(name, other) >= threshold
                   for other, _t in cluster["members"]):
                cluster["members"].append((name, kind))
                for key in keys:
                    if position not in index[key]:
                        index[key].append(position)
                placed = True
                break

        if not placed:
            clusters.append({"kind": kind, "members": [(name, kind)]})
            for key in keys:
                index[key].append(len(clusters) - 1)

    out = []
    for cluster in clusters:
        canonical = max((n for n, _t in cluster["members"]), key=_canonical_rank)
        out.append(Cluster(canonical, cluster["kind"], cluster["members"]))
    return out


def _canonical_rank(name):
    """How good a name is as the display form.

    Most letters first, so "Acme Corporation" beats "Acme". Then *fewest*
    punctuation marks, which is what stops "Vane, Aldric" beating "Aldric Vane"
    purely by being one character longer — a comma is not extra information,
    and an inverted name is a worse label than a natural one.
    """
    letters = sum(c.isalnum() for c in name)
    punctuation = sum(not c.isalnum() and not c.isspace() for c in name)
    return (letters, -punctuation, len(name))


class Ontology:
    """The maintained vocabulary: canonical entities, aliases, and types.

    "Maintained" is the operative word from the constitution — this is a thing
    that is *kept*, so a name resolved once stays resolved. Without that, every
    ingest re-decides, and the same document can produce different entities on
    two different days.
    """

    def __init__(self):
        self._canonical = {}    # normalised alias -> canonical name
        self._types = {}        # canonical name -> type
        self._aliases = defaultdict(set)

    def declare(self, canonical, kind="concept", aliases=()):
        canonical = canonical.strip()
        self._types[canonical] = (kind or "concept").lower()
        for alias in (canonical, *aliases):
            key = normalize(alias)
            if key:
                self._canonical[key] = canonical
                if alias.strip() != canonical:
                    self._aliases[canonical].add(alias.strip())
        return canonical

    def learn(self, clusters):
        """Absorb a resolution pass into the maintained vocabulary."""
        for cluster in clusters:
            self.declare(cluster.canonical, cluster.kind,
                         aliases=[n for n, _t in cluster.members])
        return self

    def canonical_for(self, name, threshold=MERGE_THRESHOLD):
        """The canonical form of a name, or `None` if it is unknown.

        Exact normalised lookup first, then fuzzy — so the common case is a
        dictionary hit and the expensive scan only runs for genuinely new
        surface forms.
        """
        key = normalize(name)
        if not key:
            return None
        if key in self._canonical:
            return self._canonical[key]
        best, best_score = None, 0.0
        for known_key, canonical in self._canonical.items():
            score = name_similarity(key, known_key)
            if score >= threshold and score > best_score:
                best, best_score = canonical, score
        return best

    def type_of(self, canonical):
        return self._types.get(canonical)

    def aliases_of(self, canonical):
        return sorted(self._aliases.get(canonical, ()))

    @property
    def entities(self):
        return sorted(self._types)

    def summary(self):
        return {
            "entities": len(self._types),
            "aliases": sum(len(v) for v in self._aliases.values()),
            "types": sorted(set(self._types.values())),
        }
