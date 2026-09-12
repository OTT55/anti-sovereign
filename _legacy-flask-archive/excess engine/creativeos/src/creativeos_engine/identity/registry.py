"""The Identity Engine's storage: external references and merge aliases.

Constitution v2.0: *"Every entity receives a persistent identity. Identity
survives renames. Identity survives movement. **Identity survives
applications.** Everything has one identity."*

Phase 1 delivered the first three — an `ENT-…` id that never moves. This module
delivers the fourth, which is the hard one. FrameVault knows a person as
`user 7`, FilmCrew knows the same person as `talent 12`, RightsForge as
`seller 4`. Today nothing can state that those are one person, so the graph
holds three strangers.

Two mechanisms:

* **External references** — an application registers its own key for an entity.
  `(framevault, user, 7) -> ENT-9F3A`. Resolution is then a lookup, and the
  application never has to store CreativeOS ids it would have to keep in sync.

* **Merge aliases** — when two entities turn out to be the same thing, one
  becomes an alias of the other. Nothing is deleted and no assertion is
  rewritten: the losing id keeps resolving, forever, to the surviving entity.
  That is what makes a merge safe to perform on a graph other applications
  already hold references into.
"""

import re
from dataclasses import dataclass

SCHEMA = """
CREATE TABLE IF NOT EXISTS external_refs (
    system      TEXT NOT NULL,
    ref_kind    TEXT NOT NULL,
    external_id TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    space_id TEXT NOT NULL,
    linked_at   TEXT NOT NULL,
    PRIMARY KEY (system, ref_kind, external_id)
);

CREATE TABLE IF NOT EXISTS identity_aliases (
    alias_id     TEXT PRIMARY KEY,
    canonical_id TEXT NOT NULL,
    merged_at    TEXT NOT NULL,
    reason       TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_external_entity ON external_refs(entity_id);
CREATE INDEX IF NOT EXISTS idx_alias_canonical ON identity_aliases(canonical_id);
"""


class IdentityError(Exception):
    """Raised when a link or merge would make identity incoherent."""


@dataclass(frozen=True)
class ExternalRef:
    """One application's own key for an entity."""

    system: str        # "framevault", "filmcrew", "rightsforge"
    ref_kind: str      # "user", "talent", "seller"
    external_id: str   # "7"
    entity_id: str
    space_id: str
    linked_at: str

    def describe(self):
        return f"{self.system}:{self.ref_kind}:{self.external_id}"


class IdentityRegistry:
    """External references and merge aliases. Shares the graph's connection."""

    def __init__(self, conn):
        self.conn = conn
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # -- external references ------------------------------------------------

    def link(self, system, ref_kind, external_id, entity_id, space_id, linked_at):
        existing = self.lookup(system, ref_kind, external_id)
        if existing is not None and existing.entity_id != entity_id:
            raise IdentityError(
                f"{system}:{ref_kind}:{external_id} is already linked to "
                f"{existing.entity_id}. Merge the entities instead of relinking — "
                "silently repointing an external reference would strand every fact "
                "recorded against the old entity."
            )
        self.conn.execute(
            """INSERT OR REPLACE INTO external_refs
               (system, ref_kind, external_id, entity_id, space_id, linked_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (system, ref_kind, str(external_id), entity_id, space_id, linked_at),
        )
        self.conn.commit()
        return ExternalRef(system, ref_kind, str(external_id), entity_id, space_id, linked_at)

    def lookup(self, system, ref_kind, external_id):
        row = self.conn.execute(
            """SELECT * FROM external_refs
               WHERE system = ? AND ref_kind = ? AND external_id = ?""",
            (system, ref_kind, str(external_id)),
        ).fetchone()
        return self._to_ref(row) if row else None

    def refs_for(self, entity_ids):
        """Every external reference pointing at any id in a merge group."""
        placeholders = ",".join("?" for _ in entity_ids)
        rows = self.conn.execute(
            f"SELECT * FROM external_refs WHERE entity_id IN ({placeholders}) "
            "ORDER BY system ASC, ref_kind ASC",
            list(entity_ids),
        ).fetchall()
        return [self._to_ref(r) for r in rows]

    @staticmethod
    def _to_ref(row):
        return ExternalRef(
            system=row["system"], ref_kind=row["ref_kind"], external_id=row["external_id"],
            entity_id=row["entity_id"], space_id=row["space_id"],
            linked_at=row["linked_at"],
        )

    # -- merge aliases ------------------------------------------------------

    def add_alias(self, alias_id, canonical_id, merged_at, reason=""):
        self.conn.execute(
            """INSERT OR REPLACE INTO identity_aliases
               (alias_id, canonical_id, merged_at, reason) VALUES (?, ?, ?, ?)""",
            (alias_id, canonical_id, merged_at, reason),
        )
        self.conn.commit()

    def canonical_id(self, entity_id):
        """Follow the alias chain to the surviving entity.

        Chains occur naturally: merge B into A, later merge A into C, and B must
        still resolve to C. Guarded against cycles, which a badly ordered pair of
        merges could otherwise create.
        """
        seen = {entity_id}
        current = entity_id
        while True:
            row = self.conn.execute(
                "SELECT canonical_id FROM identity_aliases WHERE alias_id = ?", (current,)
            ).fetchone()
            if row is None:
                return current
            current = row["canonical_id"]
            if current in seen:
                raise IdentityError(f"Alias cycle detected involving {entity_id}.")
            seen.add(current)

    def aliases_of(self, canonical_id):
        """Every id that resolves to this one, directly or through a chain."""
        found, frontier = set(), [canonical_id]
        while frontier:
            current = frontier.pop()
            rows = self.conn.execute(
                "SELECT alias_id FROM identity_aliases WHERE canonical_id = ?", (current,)
            ).fetchall()
            for r in rows:
                if r["alias_id"] not in found:
                    found.add(r["alias_id"])
                    frontier.append(r["alias_id"])
        return found

    def identity_group(self, entity_id):
        """The canonical id plus every id ever merged into it — the set of ids
        that facts about this thing might be recorded against."""
        canonical = self.canonical_id(entity_id)
        return {canonical} | self.aliases_of(canonical)

    def is_alias(self, entity_id):
        row = self.conn.execute(
            "SELECT 1 FROM identity_aliases WHERE alias_id = ?", (entity_id,)
        ).fetchone()
        return row is not None

    # -- suggesting merges -------------------------------------------------

    def suggest_merges(self, entities, threshold=0.85, limit=50):
        """Entities that look like the same thing, ranked by confidence.

        With several applications writing into one graph, duplicates are not a
        possibility but a certainty — FilmCrew's "Aldric Vane" and RightsForge's
        "A. Vane" arrive independently and nothing connects them. `merge_entities`
        could always fix that; nothing could *find* it.

        **Suggests, never merges.** A merge is consequential and hard to reverse,
        so this returns candidates for a human to confirm. That is the same rule
        the rest of the platform follows: decide deterministically, act only on
        what someone approved.

        `entities` is the list to consider — usually `graph.find_entities(space)`.
        """
        by_kind = {}
        for entity in entities:
            if self.is_alias(entity.id):
                continue   # already merged away
            by_kind.setdefault(entity.kind, []).append(entity)

        suggestions = []
        for kind, group in by_kind.items():
            # Blocked by shared token initial, so this stays linear-ish rather
            # than comparing every entity against every other.
            index = {}
            for entity in group:
                for initial in _initials(entity.name):
                    index.setdefault(initial, []).append(entity)

            seen_pairs = set()
            for entity in group:
                candidates = {other.id: other
                              for initial in _initials(entity.name)
                              for other in index.get(initial, ())
                              if other.id != entity.id}
                for other in candidates.values():
                    pair = tuple(sorted((entity.id, other.id)))
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)
                    score = _name_similarity(entity.name, other.name)
                    if score >= threshold:
                        suggestions.append(MergeSuggestion(entity, other, score, kind))

        suggestions.sort(key=lambda s: (-s.score, s.keep.name, s.merge.name))
        return suggestions[:limit]


class MergeSuggestion:
    """Two entities that look like one, for a human to confirm."""

    __slots__ = ("keep", "merge", "score", "kind")

    def __init__(self, left, right, score, kind):
        # The fuller name survives — it is the more useful label and the one a
        # reader can disambiguate.
        ordered = sorted((left, right), key=lambda e: _rank(e.name), reverse=True)
        self.keep, self.merge = ordered[0], ordered[1]
        self.score = round(score, 4)
        self.kind = kind

    def describe(self):
        return (f"'{self.merge.name}' may be the same {self.kind} as "
                f"'{self.keep.name}' ({self.score:.2f})")

    def __repr__(self):
        return f"<MergeSuggestion {self.describe()}>"


#: Words that carry no identity — two names differing only by these are the
#: same thing. Titles matter as much as legal forms here: FilmCrew records
#: "Chancellor Aldric Vane" and RightsForge records "Aldric Vane", and without
#: stripping the rank those score 0.71 and never meet.
_NOISE = {
    # legal forms
    "inc", "incorporated", "corp", "corporation", "co", "company", "ltd",
    "limited", "llc", "llp", "plc", "gmbh", "sa", "ag", "nv", "bv", "pty",
    "group", "holdings", "holding",
    # honorifics and ranks
    "mr", "mrs", "ms", "miss", "dr", "prof", "professor", "sir", "dame",
    "lord", "lady", "king", "queen", "prince", "princess", "emperor",
    "empress", "duke", "duchess", "baron", "count", "countess", "regent",
    "chancellor", "admiral", "captain", "commander", "general", "colonel",
    "major", "sergeant", "lieutenant", "president", "director", "chief",
    "father", "mother", "brother", "sister", "saint", "st",
    # articles
    "the", "a", "an", "and", "of",
}


def _normalize(name):
    cleaned = re.sub(r"[^\w\s]", " ", (name or "").lower())
    return " ".join(t for t in cleaned.split() if t and t not in _NOISE)


def _initials(name):
    return {token[0] for token in _normalize(name).split() if token} or {""}


def _rank(name):
    letters = sum(c.isalnum() for c in name)
    punctuation = sum(not c.isalnum() and not c.isspace() for c in name)
    return (letters, -punctuation, len(name))


def _numbers(text):
    return tuple(re.findall(r"\d+", text or ""))


def _name_similarity(left, right):
    """Character-bigram Dice over normalised names, with a numbers veto.

    The veto matters as much here as it does for documents: "Production 12" and
    "Production 13" share every bigram but two, and merging them would attach
    one production's crew and contracts to another.
    """
    a, b = _normalize(left), _normalize(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if _numbers(a) != _numbers(b):
        return 0.0
    ga = {f" {a} "[i:i + 2] for i in range(len(a) + 1)}
    gb = {f" {b} "[i:i + 2] for i in range(len(b) + 1)}
    if not ga or not gb:
        return 0.0
    return 2 * len(ga & gb) / (len(ga) + len(gb))
