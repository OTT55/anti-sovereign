"""The Creative Knowledge Graph's data model.

Three ideas carry the whole design:

1. **Everything is an entity.** Characters, scenes, locations, magic systems,
   assets, rights, studios — one node type with a `kind`, not a separate table
   per concept. New creative concepts must not require a schema migration.

   Under Constitution v2.0 the core does not know what any of those *are*: an
   entity's `kind` is a string an application declared through a `DomainPack`
   (see `types.py`). CreativeOS enforces that the type exists; only the
   application knows what it means.

2. **Nothing is edited or deleted — facts are asserted and retracted.** An
   `Assertion` is one creator saying one thing, with provenance. Changing your
   mind retracts the old assertion and adds a new one; both stay on the record.
   This is what makes "what changed?", retcon tracking, and branching possible
   at all — and it is the Memory Engine's core promise that nothing is
   forgotten.

3. **Two independent clocks.** See `ValidWindow` below — this is the decision
   that makes contradiction detection computable rather than manual.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AssertionKind(str, Enum):
    ATTRIBUTE = "attribute"        # subject --predicate--> literal value
    RELATIONSHIP = "relationship"  # subject --predicate--> another entity


@dataclass(frozen=True)
class ValidWindow:
    """When a fact is true **in the world the assertion describes**, as a
    half-open interval `[start, end)` on that world's own clock.

    `None` means unbounded — `ValidWindow(None, None)` is "always true," the
    right default for something like a character's species or an asset's author.

    **Why valid time is separate from record time.** A creator writing on
    Tuesday can assert a fact about the year 1147 of their world. Those are two
    different clocks, and conflating them makes contradiction checking
    impossible:

      * *Valid time* answers "was Aragorn king at tick 300?"
      * *Record time* answers "did the author still believe that on Tuesday, or
        had they retconned it by then?"

    A contradiction is two live assertions that disagree while their valid
    windows overlap. A retcon is the author retracting one — which changes the
    record-time answer but not the valid-time question. You need both axes to
    tell those apart, and telling them apart is the whole job of the
    Verification Engine.

    Valid time is a plain integer tick, deliberately. Real calendars (regnal
    years, multiple moons, era resets, fiscal quarters) are an *application's*
    job; forcing one calendar into the graph core would bake a single domain's
    cosmology into every domain's storage.

    Named for the standard bitemporal term (valid time vs. record time) rather
    than "story time", because under Constitution v2.0 the core must not assume
    the world it is describing is a story. It might be a production schedule or
    a rights chain.
    """

    start: Optional[int] = None
    end: Optional[int] = None

    def __post_init__(self):
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise ValueError(
                f"ValidWindow start ({self.start}) must be before end ({self.end}); "
                "the window is half-open [start, end)."
            )

    def contains(self, tick):
        """Is `tick` inside this window?"""
        if self.start is not None and tick < self.start:
            return False
        if self.end is not None and tick >= self.end:
            return False
        return True

    def overlaps(self, other):
        """Do these two windows share any valid time at all?

        Two facts can only contradict each other if their windows overlap —
        "alive until tick 300" and "dead from tick 300" is continuity, not
        conflict. This method is what draws that line.
        """
        if self.start is not None and other.end is not None and self.start >= other.end:
            return False
        if other.start is not None and self.end is not None and other.start >= self.end:
            return False
        return True

    def describe(self):
        if self.start is None and self.end is None:
            return "always"
        if self.start is None:
            return f"until {self.end}"
        if self.end is None:
            return f"from {self.start}"
        return f"{self.start}–{self.end}"


@dataclass
class Space:
    """One creative space. The outermost container: entities never cross
    spaces, so two projects can both have a "Council" with no collision.

    `domain` names the application vocabulary in play (film, novel, game,
    rights, production...) — the Domain Engine specializes on this.
    """

    id: str
    name: str
    domain: str
    created_at: str


@dataclass
class Entity:
    """A node. Identity only — everything *about* it lives in assertions, so
    that every fact carries its own provenance and history.

    `kind` is a declared domain type (a plain string, see `types.py`), not a
    value from a core enum. The Identity Engine's promise lives here: this `id`
    is stable across renames, moves, and applications.
    """

    id: str
    space_id: str
    kind: str
    name: str
    created_at: str
    subkind: str = ""  # free-text refinement, e.g. kind="artifact" subkind="sword"


@dataclass
class Assertion:
    """One sourced claim about the space, valid over a window of valid time.

    Never mutated after insert. Retraction sets `retracted_at`, preserving what
    was believed and when — the record of a retcon, not its erasure.
    """

    id: str
    space_id: str
    kind: AssertionKind
    subject_id: str
    predicate: str
    valid: ValidWindow
    recorded_at: str
    object_value: Optional[str] = None   # ATTRIBUTE: the literal value
    object_id: Optional[str] = None      # RELATIONSHIP: the target entity
    source_kind: str = "authored"        # manuscript, note, transcript, import, authored...
    source_ref: str = ""                 # locator within that source: page, scene id, timecode
    confidence: float = 1.0
    retracted_at: Optional[str] = None
    retraction_reason: str = ""

    @property
    def is_retracted(self):
        return self.retracted_at is not None

    def object_repr(self):
        return self.object_value if self.kind == AssertionKind.ATTRIBUTE else self.object_id


@dataclass
class Contradiction:
    """Two live assertions that say different things about the same subject and
    predicate while their valid windows overlap.

    This is the graph's deterministic answer to "What contradicts it?" — no
    model call, no heuristic. The Verification Engine layers judgement-based
    rules on top; this is the floor those rules stand on.
    """

    subject_id: str
    predicate: str
    left: Assertion
    right: Assertion

    def describe(self):
        return (
            f"{self.predicate}: '{self.left.object_repr()}' ({self.left.valid.describe()}) "
            f"vs '{self.right.object_repr()}' ({self.right.valid.describe()})"
        )
