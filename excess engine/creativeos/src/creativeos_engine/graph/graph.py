"""`CreativeGraph` — the one API every CreativeOS engine reads and writes.

This is the substrate Constitution v2.0 demands: *"Applications contribute to
the graph. CreativeOS maintains it."* Four of the core engines are literally
methods on this class:

    Identity Engine      -> create_entity / get_entity   (ids stable forever)
    Graph Engine         -> relationships_of / neighbors
    Memory Engine        -> history_of                   (retractions kept)
    Verification Engine  -> contradictions               (deterministic)
    Context Engine       -> context_of                   (the whole bundle)

Deliberately contains no model calls and no framework. The graph must be
deterministic and fast, because every other engine queries it constantly and
the Verification Engine needs its answers to be *provably* right rather than
plausible.

**It knows no domain vocabulary.** It cannot tell you what a character is. It
can only tell you that an entity of a type some application declared has these
facts, these relationships, this history, and these contradictions. That
ignorance is the design, not a gap in it.
"""

from itertools import combinations

from . import ids
from ..events.model import EventKind
from ..identity import IdentityError
from .model import Assertion, AssertionKind, Contradiction, Entity, Space, ValidWindow
from .types import DomainPack, TypeError_, normalize_type


class GraphError(Exception):
    """Raised when an operation would put the graph in an incoherent state."""


class CreativeGraph:
    def __init__(self, db_path=":memory:", store=None, bus=None, identity=None):
        from .store import GraphStore
        self.store = store or GraphStore(db_path)
        if bus is None:
            # The bus shares the graph's connection so a write and the event
            # announcing it land in the same database and cannot disagree.
            from ..events import EventBus
            bus = EventBus(self.store.conn)
        self.bus = bus
        if identity is None:
            from ..identity import IdentityRegistry
            identity = IdentityRegistry(self.store.conn)
        self.identity = identity

    #: Which application or engine is credited as the cause of core events.
    SOURCE = "creativeos.graph"

    def _emit(self, space_id, event_kind, subject_id="", payload=None):
        """Payload is an explicit dict, not **kwargs: a payload key called
        `kind` or `source` would otherwise collide with a parameter name."""
        return self.bus.publish(space_id, event_kind, subject_id, payload or {},
                                source=self.SOURCE)

    # -- spaces & the declared vocabulary --------------------------------

    def create_space(self, name, domain="general", pack=None):
        """Create a space, optionally installing an application's `DomainPack`.

        With no pack the space has **no entity types and no functional
        predicates** — deliberately. The core ships no vocabulary, so an
        application must declare what it intends to store before it can store
        it. That is the v2.0 boundary made mechanical rather than aspirational.
        """
        space = Space(id=ids.new_id(ids.SPACE), name=name, domain=domain,
                            created_at=ids.now())
        self.store.add_space(space)
        self._emit(space.id, EventKind.SPACE_CREATED, space.id,
                   {"name": name, "domain": domain})
        if pack is not None:
            self.install_pack(space.id, pack)
        return space

    def install_pack(self, space_id, pack):
        """Register an application's vocabulary against a space.

        Packs are additive: two applications can both contribute to one
        space, which is exactly the point of a shared graph — StoryAtlas and
        FilmCrew describing the same production without either owning it.
        """
        if not isinstance(pack, DomainPack):
            raise GraphError("pack must be a DomainPack.")
        self._require_space(space_id)
        for type_name in pack.entity_types:
            self.store.declare_entity_type(space_id, type_name)
        for predicate in pack.functional_predicates:
            self.store.declare_functional(space_id, predicate)
        self._emit(space_id, EventKind.PACK_INSTALLED, space_id,
                   {"pack": pack.name, "entity_types": list(pack.entity_types),
                    "functional_predicates": list(pack.functional_predicates)})

    def declare_entity_type(self, space_id, type_name):
        self._require_space(space_id)
        type_name = normalize_type(type_name)
        self.store.declare_entity_type(space_id, type_name)
        self._emit(space_id, EventKind.TYPE_DECLARED, space_id,
                   {"type_name": type_name})

    def entity_types(self, space_id):
        return self.store.entity_types(space_id)

    def declare_functional(self, space_id, predicate):
        self.store.declare_functional(space_id, predicate)

    def undeclare_functional(self, space_id, predicate):
        self.store.undeclare_functional(space_id, predicate)

    # -- entities -----------------------------------------------------------

    def create_entity(self, space_id, kind, name, subkind=""):
        """Create a node of a **declared** type.

        Rejecting undeclared types is what stops domain vocabulary leaking into
        the core by accident: there is no way to quietly invent a `scene` here
        without an application having said `scene` exists.
        """
        self._require_space(space_id)
        try:
            kind = normalize_type(kind)
        except TypeError_ as e:
            raise GraphError(str(e)) from e

        declared = self.store.entity_types(space_id)
        if kind not in declared:
            known = ", ".join(sorted(declared)) or "none yet"
            raise GraphError(
                f"Entity type '{kind}' was never declared for this space. "
                f"Declared types: {known}. Install a DomainPack or call "
                "declare_entity_type() first — CreativeOS ships no vocabulary of its own."
            )

        entity = Entity(id=ids.new_id(ids.ENTITY), space_id=space_id,
                        kind=kind, subkind=subkind, name=name, created_at=ids.now())
        self.store.add_entity(entity)
        self._emit(space_id, EventKind.ENTITY_CREATED, entity.id,
                   {"kind": kind, "subkind": subkind, "name": name})
        return entity

    def get_entity(self, entity_id):
        """Fetch an entity, resolving through any merge it was involved in.

        Asking for a merged-away id returns the surviving entity rather than a
        tombstone — an application holding the old id keeps working.
        """
        return self.store.get_entity(self.identity.canonical_id(entity_id))

    def find_entities(self, space_id, kind=None, name=None):
        return self.store.find_entities(
            space_id, kind=normalize_type(kind) if kind else None, name=name
        )

    def rename_entity(self, entity_id, new_name):
        """Identity Engine: *"Identity survives renames."* The id never moves,
        so every assertion and relationship pointing at this entity stays
        intact — which is the whole reason names are not identifiers here."""
        entity = self._require_entity(entity_id)
        self.store.rename_entity(entity_id, new_name)
        self._emit(entity.space_id, EventKind.ENTITY_RENAMED, entity_id,
                   {"old_name": entity.name, "new_name": new_name})
        return self.store.get_entity(entity_id)

    # -- identity across applications --------------------------------------

    def link_external(self, entity_id, system, ref_kind, external_id):
        """Register an application's own key for an entity.

        FrameVault calls this with `("framevault", "user", 7)`. It then resolves
        by its own key forever and never has to store a CreativeOS id it would
        have to keep in sync.
        """
        entity = self._require_entity(entity_id)
        try:
            ref = self.identity.link(system, ref_kind, external_id, entity.id,
                                     entity.space_id, ids.now())
        except IdentityError as e:
            raise GraphError(str(e)) from e
        self._emit(entity.space_id, EventKind.IDENTITY_LINKED, entity.id,
                   {"system": system, "ref_kind": ref_kind, "external_id": str(external_id)})
        return ref

    def resolve_external(self, system, ref_kind, external_id):
        """Find the entity an application's key points at, or `None`.

        Resolves through merges, so a key linked before a merge still returns
        the surviving entity rather than a tombstone.
        """
        ref = self.identity.lookup(system, ref_kind, external_id)
        if ref is None:
            return None
        return self.get_entity(ref.entity_id)

    def external_refs_of(self, entity_id):
        """Every application key that points at this thing — the answer to
        "who else knows about this?"."""
        return self.identity.refs_for(self._identity_group(entity_id))

    def merge_entities(self, keep_id, merge_id, reason=""):
        """Declare that two entities are the same thing.

        Nothing is deleted and no assertion is rewritten. `merge_id` becomes an
        alias: it keeps resolving to the surviving entity forever, so any
        application still holding the old id is not broken by a merge it never
        heard about. Facts recorded against either id are visible from the
        survivor.
        """
        keep = self._require_entity(keep_id)
        merged = self._require_entity(merge_id)
        if keep.id == merged.id:
            raise GraphError("Cannot merge an entity into itself.")
        if keep.space_id != merged.space_id:
            raise GraphError(
                f"Cannot merge across spaces ({merged.space_id} -> {keep.space_id})."
            )
        self.identity.add_alias(merged.id, keep.id, ids.now(), reason)
        self._emit(keep.space_id, EventKind.IDENTITY_MERGED, keep.id,
                   {"merged_id": merged.id, "merged_name": merged.name, "reason": reason})
        return self.get_entity(keep.id)

    def canonical_id(self, entity_id):
        """The surviving id for this thing, following any merges."""
        return self.identity.canonical_id(entity_id)

    def suggest_merges(self, space_id, threshold=0.85, limit=50):
        """Entities that look like the same thing, for a human to confirm.

        `merge_entities` could always fix a duplicate; nothing could *find*
        one. With several applications writing into one graph, duplicates are
        a certainty rather than a risk.

        Suggests only — a merge is consequential and hard to reverse, so
        nothing here acts on its own.
        """
        return self.identity.suggest_merges(
            self.find_entities(space_id), threshold=threshold, limit=limit)

    def _identity_group(self, entity_id):
        """Every id facts about this thing might be recorded against."""
        return self.identity.identity_group(entity_id)

    # -- asserting facts ---------------------------------------------------

    def assert_attribute(self, subject_id, predicate, value, valid=None,
                         source_kind="authored", source_ref="", confidence=1.0):
        """Claim that `subject.predicate == value` over a window of valid time."""
        subject = self._require_entity(subject_id)
        return self._add(Assertion(
            id=ids.new_id(ids.ASSERTION), space_id=subject.space_id,
            kind=AssertionKind.ATTRIBUTE, subject_id=subject_id, predicate=predicate,
            object_value=str(value), valid=valid or ValidWindow(), recorded_at=ids.now(),
            source_kind=source_kind, source_ref=source_ref, confidence=confidence,
        ))

    def assert_relationship(self, subject_id, predicate, object_id, valid=None,
                            source_kind="authored", source_ref="", confidence=1.0):
        """Connect two entities over a window of valid time. Both must exist, in
        the same space — a relationship that crosses spaces is a bug, not
        a crossover; crossovers are modelled as their own space later."""
        subject = self._require_entity(subject_id)
        target = self._require_entity(object_id)
        if subject.space_id != target.space_id:
            raise GraphError(
                f"Cannot relate entities across spaces "
                f"({subject.space_id} -> {target.space_id})."
            )
        return self._add(Assertion(
            id=ids.new_id(ids.ASSERTION), space_id=subject.space_id,
            kind=AssertionKind.RELATIONSHIP, subject_id=subject_id, predicate=predicate,
            object_id=object_id, valid=valid or ValidWindow(), recorded_at=ids.now(),
            source_kind=source_kind, source_ref=source_ref, confidence=confidence,
        ))

    def retract(self, assertion_id, reason=""):
        """Stop believing a fact without erasing that it was once believed.

        This is how a retcon is recorded: the assertion stays queryable via
        `history_of()` and via any `as_of` earlier than the retraction, but
        drops out of current state. The Memory Engine's "nothing is forgotten."
        """
        existing = self.store.get_assertion(assertion_id)
        if existing is None:
            raise GraphError(f"No such assertion: {assertion_id}")
        retracted = self.store.retract_assertion(assertion_id, ids.now(), reason)
        if retracted:
            self._emit(existing.space_id, EventKind.ASSERTION_RETRACTED, existing.subject_id,
                       {"assertion_id": assertion_id, "predicate": existing.predicate,
                        "reason": reason})
        return retracted

    def _add(self, assertion):
        self.store.add_assertion(assertion)
        self._emit(assertion.space_id, EventKind.ASSERTION_ADDED, assertion.subject_id,
                   {"assertion_id": assertion.id, "predicate": assertion.predicate,
                    "object": assertion.object_repr(),
                    "assertion_kind": assertion.kind.value,
                    "valid": [assertion.valid.start, assertion.valid.end],
                    "source_kind": assertion.source_kind,
                    "confidence": assertion.confidence})
        return assertion

    def _require_entity(self, entity_id):
        entity = self.get_entity(entity_id)
        if entity is None:
            raise GraphError(f"No such entity: {entity_id}")
        return entity

    def _require_space(self, space_id):
        space = self.store.get_space(space_id)
        if space is None:
            raise GraphError(f"No such space: {space_id}")
        return space

    # -- reading state -----------------------------------------------------

    @staticmethod
    def _is_live(assertion, as_of):
        """Was this assertion believed at record time `as_of`?
        `as_of=None` means "right now" — i.e. simply not retracted."""
        if as_of is None:
            return assertion.retracted_at is None
        if assertion.recorded_at > as_of:
            return False
        return assertion.retracted_at is None or assertion.retracted_at > as_of

    def _live_assertions(self, subject_id, at=None, as_of=None, kind=None):
        """Gathers across the whole identity group, so facts recorded against an
        id that was later merged away are still visible from the survivor."""
        result = []
        for member_id in sorted(self._identity_group(subject_id)):
            for a in self.store.assertions_about(member_id, kind=kind):
                if not self._is_live(a, as_of):
                    continue
                if at is not None and not a.valid.contains(at):
                    continue
                result.append(a)
        return result

    def state_assertions(self, entity_id, at=None, as_of=None):
        """Current attribute assertions, keyed by predicate.

        When two live assertions share a predicate, the most recently recorded
        one wins — later authoring overrides earlier. Pass `at` to ask the
        question at a moment of valid time ("what was true at tick 300?"); leave
        it `None` to ignore valid time entirely.
        """
        winners = {}
        for a in self._live_assertions(entity_id, at=at, as_of=as_of,
                                       kind=AssertionKind.ATTRIBUTE):
            current = winners.get(a.predicate)
            if current is None or (a.recorded_at, a.id) > (current.recorded_at, current.id):
                winners[a.predicate] = a
        return winners

    def state_of(self, entity_id, at=None, as_of=None):
        """Plain `{predicate: value}` view of `state_assertions`."""
        return {p: a.object_value for p, a in self.state_assertions(entity_id, at, as_of).items()}

    def relationships_of(self, entity_id, at=None, as_of=None, direction="out"):
        """Live relationships touching this entity.

        `direction`: "out" (this entity is the subject), "in" (it is the
        target), or "both" — because "how is it connected?" is rarely a
        one-way question.
        """
        if direction not in ("out", "in", "both"):
            raise GraphError("direction must be 'out', 'in', or 'both'")

        found = []
        if direction in ("out", "both"):
            found += self._live_assertions(entity_id, at=at, as_of=as_of,
                                           kind=AssertionKind.RELATIONSHIP)
        if direction in ("in", "both"):
            for member_id in sorted(self._identity_group(entity_id)):
                for a in self.store.assertions_targeting(member_id):
                    if not self._is_live(a, as_of):
                        continue
                    if at is not None and not a.valid.contains(at):
                        continue
                    found.append(a)
        return sorted(found, key=lambda a: (a.recorded_at, a.id))

    def neighbors(self, entity_id, at=None, as_of=None, direction="both"):
        """Relationships resolved into `(assertion, other_entity)` pairs."""
        group = self._identity_group(entity_id)
        pairs = []
        for a in self.relationships_of(entity_id, at=at, as_of=as_of, direction=direction):
            other_id = a.object_id if a.subject_id in group else a.subject_id
            other = self.get_entity(other_id)
            if other is not None:
                pairs.append((a, other))
        return pairs

    def history_of(self, entity_id):
        """Every assertion ever made about this entity, oldest first, including
        retracted ones. The Memory Engine's full record — what retcon tracking
        reads.

        Spans the identity group: after a merge, the survivor's history includes
        everything recorded against the id that was merged away. Nothing is
        forgotten, which is the point.
        """
        found = []
        for member_id in sorted(self._identity_group(entity_id)):
            found += self.store.assertions_about(member_id)
        return sorted(found, key=lambda a: (a.recorded_at, a.id))

    # -- contradiction detection ------------------------------------------

    def contradictions(self, space_id, entity_id=None, as_of=None):
        """Live assertions that disagree: same subject, same *functional*
        predicate, different value, overlapping valid windows.

        Purely deterministic — no model call, no guessing. The Verification
        Engine adds rules that need judgement on top; this is the floor those
        rules build on, and it should never produce a false positive.

        A space with no declared functional predicates reports nothing, since
        without knowing which predicates are single-valued the core cannot tell
        a contradiction from a character who is legitimately both brave and
        reckless. That knowledge is the application's to supply.
        """
        functional = self.store.functional_predicates(space_id)
        if not functional:
            return []

        if entity_id is not None:
            source = []
            for member_id in sorted(self._identity_group(entity_id)):
                source += self.store.assertions_about(member_id)
        else:
            source = self.store.assertions_in_space(space_id)

        by_key = {}
        for a in source:
            if a.predicate not in functional or not self._is_live(a, as_of):
                continue
            # Group by canonical id: after a merge, facts recorded against the
            # old and new ids describe one thing and so *can* contradict.
            subject_key = self.identity.canonical_id(a.subject_id)
            by_key.setdefault((subject_key, a.predicate), []).append(a)

        found = []
        for (subject_id, predicate), group in sorted(by_key.items()):
            for left, right in combinations(group, 2):
                if left.object_repr() == right.object_repr():
                    continue
                if not left.valid.overlaps(right.valid):
                    continue
                found.append(Contradiction(subject_id=subject_id, predicate=predicate,
                                           left=left, right=right))
        return found

    # -- the whole picture -------------------------------------------------

    def context_of(self, entity_id, at=None, as_of=None):
        """Everything the graph knows about one entity, at one moment.

        This is the Context Engine's primitive — *"assembles relevant
        information across every application"* — and it answers the
        constitution's questions in one call: what exists (identity), what it
        means (state), how it is connected (relationships), what changed
        (history), what contradicts it (contradictions). The Intelligence
        Engine consumes exactly this shape.
        """
        entity = self._require_entity(entity_id)
        history = self.history_of(entity_id)
        group = self._identity_group(entity_id)
        return {
            "entity": entity,
            "state": self.state_of(entity_id, at=at, as_of=as_of),
            "relationships": self.neighbors(entity_id, at=at, as_of=as_of),
            "history_count": len(history),
            "retracted_count": sum(1 for a in history if a.is_retracted),
            "sources": sorted({a.source_kind for a in history}),
            "contradictions": self.contradictions(entity.space_id, entity_id=entity_id,
                                                  as_of=as_of),
            # Which applications know about this thing, and under what key.
            "external_refs": self.external_refs_of(entity_id),
            "merged_ids": sorted(group - {entity.id}),
        }

    def close(self):
        self.store.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
