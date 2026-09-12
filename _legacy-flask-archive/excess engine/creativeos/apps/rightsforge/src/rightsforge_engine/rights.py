"""The rights ledger: who may do what with a work, where, and until when.

RightsForge's domain authority. CreativeOS understands that two records are
related; RightsForge understands that an exclusive UK film licence and an
exclusive worldwide film licence **cannot both be sold**, and that an option
which lapsed in March stopped being anybody's in March.

## The three things a grant is made of

A grant is not "somebody bought this". It is a **scope**, a **term**, and an
**exclusivity flag**, and every interesting question is about how those three
interact:

* **Scope** — which right, which territory, which medium. Film rights in the UK
  and stage rights in the UK are different things and can go to different
  buyers on the same day.
* **Term** — a start and an end. An option is *time-limited by definition*: it
  buys the right to decide later, and when it lapses the rights revert. A
  purchase is perpetual.
* **Exclusivity** — whether granting it forbids granting anything overlapping.

Collapse any of the three and the ledger starts lying. Model a listing as a
single `status` field — `listed | optioned | sold` — and an option locks the
work **forever**, because nothing in that model can express *until when*.

## The one rule

> Two grants **collide** when their scopes overlap **and** their terms overlap
> **and** at least one of them is exclusive.

Everything else here is that sentence, evaluated. Non-exclusive licences never
collide with each other, which is exactly why an asset can be sold a thousand
times and a film option cannot be sold twice.

## On reusing interval arithmetic

The term-overlap maths is the same as StoryAtlas's lifespan reconciliation, and
it is deliberately **not** imported from there. Applications may depend on the
platform beneath them, never sideways on each other — a rights ledger that
breaks when a narrative engine is refactored is a worse outcome than twenty
lines of interval code appearing twice. If it needs sharing, it belongs in
CreativeOS, not in a sibling.
"""

#: Scope values that mean "everything on this axis". A grant with `territory
#: = ANY` overlaps every territory, which is what "worldwide" has to mean for
#: the collision check to be sound.
ANY = "*"

#: The deal kinds a grant can come from, and whether each is exclusive and
#: time-limited by nature. This table is the domain knowledge: it is *why*
#: an option behaves differently from a licence, expressed once.
KINDS = {
    #  kind        exclusive  perpetual
    "option":     (True,      False),
    "license":    (False,     False),
    "exclusive-license": (True, False),
    "purchase":   (True,      True),
    "assignment": (True,      True),
}


class RightsError(Exception):
    """Raised when a grant cannot be made as written."""


class Scope:
    """Which right, where, in what medium.

    Three axes because those are the three that actually get carved up in
    practice. A fourth ("language") would work identically — the overlap test
    does not care how many axes there are, only that each one is compared the
    same way.
    """

    __slots__ = ("right", "territory", "medium")

    def __init__(self, right, territory=ANY, medium=ANY):
        if not (right or "").strip():
            raise RightsError("A grant must name which right it covers.")
        self.right = right.strip().casefold()
        self.territory = (territory or ANY).strip().casefold()
        self.medium = (medium or ANY).strip().casefold()

    def overlaps(self, other):
        """Do these two scopes describe any of the same ground?

        Every axis must overlap. Film-in-the-UK and film-in-France share the
        right but not the territory, so they do not collide — and a marketplace
        that cannot express that cannot sell territory-by-territory, which is
        how the business actually works.
        """
        return all(
            mine == theirs or ANY in (mine, theirs)
            for mine, theirs in (
                (self.right, other.right),
                (self.territory, other.territory),
                (self.medium, other.medium),
            )
        )

    def describe(self):
        parts = [self.right]
        parts.append("worldwide" if self.territory == ANY else self.territory)
        if self.medium != ANY:
            parts.append(self.medium)
        return " · ".join(parts)

    def __eq__(self, other):
        return (isinstance(other, Scope) and self.right == other.right
                and self.territory == other.territory and self.medium == other.medium)

    def __hash__(self):
        return hash((self.right, self.territory, self.medium))

    def __repr__(self):
        return f"<Scope {self.describe()}>"


class Term:
    """When a grant runs from and until. `ends=None` is perpetual."""

    __slots__ = ("starts", "ends")

    def __init__(self, starts, ends=None):
        if ends is not None and ends < starts:
            raise RightsError(
                f"A term cannot end ({ends}) before it starts ({starts}).")
        self.starts = starts
        self.ends = ends

    @property
    def is_perpetual(self):
        return self.ends is None

    def contains(self, when):
        if when < self.starts:
            return False
        return self.ends is None or when <= self.ends

    def overlaps(self, other):
        """Interval intersection. Open ends extend forever, which is the whole
        difference between a purchase and an option."""
        if self.ends is not None and other.starts > self.ends:
            return False
        if other.ends is not None and self.starts > other.ends:
            return False
        return True

    def describe(self):
        return f"{self.starts} – {'perpetual' if self.is_perpetual else self.ends}"

    def __repr__(self):
        return f"<Term {self.describe()}>"


class Grant:
    """One right, granted to one holder, over one scope, for one term."""

    __slots__ = ("work_id", "holder", "scope", "term", "kind", "exclusive",
                 "price_pence", "grant_id", "source")

    def __init__(self, work_id, holder, scope, term, kind="license",
                 exclusive=None, price_pence=0, grant_id=None, source=""):
        if kind not in KINDS:
            raise RightsError(
                f"Unknown deal kind '{kind}'. Known: {', '.join(sorted(KINDS))}.")
        default_exclusive, perpetual = KINDS[kind]

        # An option that never ends is not an option — it is an assignment with
        # a smaller price tag, and treating it as one locks a work forever.
        if not perpetual and term.is_perpetual:
            raise RightsError(
                f"A {kind} must have an end date. Without one it never lapses, "
                "so the rights never revert and the work is locked permanently.")

        self.work_id = work_id
        self.holder = holder
        self.scope = scope
        self.term = term
        self.kind = kind
        self.exclusive = default_exclusive if exclusive is None else exclusive
        self.price_pence = price_pence
        self.grant_id = grant_id
        self.source = source

    def is_live(self, when):
        return self.term.contains(when)

    def collides_with(self, other):
        """The one rule, in one place."""
        if self.work_id != other.work_id:
            return False
        if not (self.exclusive or other.exclusive):
            return False
        return self.scope.overlaps(other.scope) and self.term.overlaps(other.term)

    def describe(self):
        lock = "exclusive" if self.exclusive else "non-exclusive"
        return (f"{self.holder}: {self.kind} ({lock}) — {self.scope.describe()} — "
                f"{self.term.describe()}")

    def __repr__(self):
        return f"<Grant {self.describe()}>"


class Conflict:
    """Two grants that cannot both be honoured, and why."""

    __slots__ = ("first", "second", "reason")

    def __init__(self, first, second, reason):
        self.first = first
        self.second = second
        self.reason = reason

    def describe(self):
        return self.reason

    def __repr__(self):
        return f"<Conflict {self.reason}>"


class Ledger:
    """Every grant made against every work, and what can still be granted.

    In-memory by design — persistence is the application's job. What lives here
    is the part an application must not reimplement: deciding whether a grant
    can be made at all.
    """

    def __init__(self):
        self.grants = []
        self._next_id = 1

    # -- writing -----------------------------------------------------------

    def check(self, grant):
        """Would this grant conflict with anything already recorded?

        Separated from `record()` so an application can *offer* a deal without
        committing to it — the same propose-then-decide shape the rest of the
        ecosystem uses. A marketplace that can only find out by trying has no
        way to show a buyer why something is unavailable.
        """
        return [
            Conflict(existing, grant, _explain(existing, grant))
            for existing in self.grants
            if existing.collides_with(grant)
        ]

    def record(self, grant):
        """Add a grant, refusing it if it conflicts.

        Refusing rather than recording-and-warning: an exclusive right granted
        twice is not a data-quality problem to be cleaned up later, it is two
        people who both believe they own something.
        """
        conflicts = self.check(grant)
        if conflicts:
            raise RightsError(conflicts[0].reason)
        grant.grant_id = f"RF-{self._next_id:05d}"
        self._next_id += 1
        self.grants.append(grant)
        return grant

    # -- reading -----------------------------------------------------------

    def for_work(self, work_id):
        return [g for g in self.grants if g.work_id == work_id]

    def live_at(self, work_id, when):
        """Grants actually in force at a moment — the question a lapsed option
        makes worth asking."""
        return [g for g in self.for_work(work_id) if g.is_live(when)]

    def holder_of(self, work_id, scope, when):
        """Who holds an exclusive right over this scope at this moment, if anyone."""
        for grant in self.live_at(work_id, when):
            if grant.exclusive and grant.scope.overlaps(scope):
                return grant
        return None

    def is_available(self, work_id, scope, term, exclusive=True):
        """Could this be granted? The buyer-facing form of `check`."""
        probe = Grant(work_id, "?", scope, term,
                      kind="exclusive-license" if exclusive else "license",
                      exclusive=exclusive)
        return not self.check(probe)

    def lapsed(self, work_id, when):
        """Grants whose term has ended — rights that have reverted to the seller.

        The list the app cannot produce at all, because a `status` column has no
        way to represent *used to be optioned*.
        """
        return [g for g in self.for_work(work_id)
                if g.term.ends is not None and g.term.ends < when]

    def timeline(self, work_id):
        """Every grant in start order, for showing a work's rights history."""
        return sorted(self.for_work(work_id),
                      key=lambda g: (g.term.starts,
                                     g.term.ends is None,
                                     g.term.ends or 0,
                                     g.grant_id or ""))

    def summary(self, work_id, when):
        live = self.live_at(work_id, when)
        return {
            "grants": len(self.for_work(work_id)),
            "live": len(live),
            "lapsed": len(self.lapsed(work_id, when)),
            "exclusive_live": sum(1 for g in live if g.exclusive),
        }


def _explain(existing, proposed):
    """Say which of the two is exclusive, because that is the part a seller
    disputes."""
    blocker = existing if existing.exclusive else proposed
    return (
        f"{blocker.holder}'s {blocker.kind} over {blocker.scope.describe()} "
        f"({blocker.term.describe()}) is exclusive and overlaps this "
        f"{proposed.kind} over {proposed.scope.describe()} "
        f"({proposed.term.describe()})."
    )


__all__ = ["ANY", "KINDS", "Scope", "Term", "Grant", "Conflict", "Ledger",
           "RightsError"]
