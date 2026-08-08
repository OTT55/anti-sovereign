"""What an event is.

Constitution v2.0, Event Engine: *"Everything emits events. Applications
communicate **only** through events. No tight coupling. CreativeOS becomes
reactive."*

An event is a statement that something already happened. It is past tense and
immutable — nothing in the system ever edits or deletes one. That is what makes
the log replayable, and replay is what lets an application that was offline (or
that did not exist yet) catch up on everything it missed.
"""

import json
from dataclasses import dataclass, field


class EventKind:
    """Event names the CreativeOS core itself emits.

    Applications emit their own kinds alongside these — `hire.completed`,
    `asset.licensed`, `ip.optioned` — which is the entire point: those are
    currently direct HTTP calls between FrameVault, FilmCrew and RightsForge,
    and v2.0 forbids that coupling.

    Names are `noun.past_tense_verb`, dot-separated, so prefix subscriptions
    (`assertion.*`) group naturally.
    """

    SPACE_CREATED = "space.created"
    TYPE_DECLARED = "type.declared"
    PACK_INSTALLED = "pack.installed"
    ENTITY_CREATED = "entity.created"
    ENTITY_RENAMED = "entity.renamed"
    ASSERTION_ADDED = "assertion.added"
    ASSERTION_RETRACTED = "assertion.retracted"
    IDENTITY_LINKED = "identity.linked"
    IDENTITY_MERGED = "identity.merged"


@dataclass(frozen=True)
class Event:
    """One thing that happened, durably recorded before anyone is told about it.

    `sequence` is a global monotonic integer assigned by the log. It is the
    ordering authority and the replay cursor — a subscriber remembers the last
    sequence it processed and asks for everything after it. Timestamps are not
    used for ordering: two events can share a timestamp, and clocks are a bad
    thing to depend on for correctness.
    """

    id: str
    sequence: int
    space_id: str
    kind: str
    subject_id: str
    payload: dict
    occurred_at: str
    source: str  # which application or engine caused this — "filmcrew", "creativeos.graph"

    def matches(self, pattern):
        """Does this event's kind match a subscription pattern?

        `"*"` matches everything, `"assertion.*"` matches every assertion event,
        and an exact name matches only itself. Deliberately simple — a
        subscription language is not a feature anyone asked for.
        """
        if pattern == "*":
            return True
        if pattern.endswith(".*"):
            return self.kind.startswith(pattern[:-1])
        return self.kind == pattern

    def describe(self):
        return f"#{self.sequence} {self.kind} {self.subject_id} (from {self.source})"


@dataclass
class DeliveryFailure:
    """A subscriber that raised while handling an event.

    Kept as data rather than allowed to propagate: one broken subscriber must
    not roll back a write that already happened, nor block the other
    subscribers. See DECISIONS.md 0008.
    """

    event: Event
    subscriber: str
    error: str

    def describe(self):
        return f"{self.subscriber} failed on {self.event.describe()}: {self.error}"


def to_json(payload):
    """Payloads are stored as JSON text, so the log stays inspectable with plain
    SQL and portable to any other store later."""
    return json.dumps(payload, sort_keys=True, default=str)


def from_json(text):
    return json.loads(text) if text else {}
