"""FrameVault's Reputation Engine — a record earned, not asserted.

The domain rule FrameVault owns: **a credit is something another application
says happened**, never something a creator claims about themselves. A résumé is
a claim; a paid contract is evidence. Reputation here is the second kind only.

This is where the ecosystem wiring pays off. FilmCrew publishes
`hire.completed` when a contract is actually paid; FrameVault listens and
credits the creator. FilmCrew holds no reference to FrameVault and does not
know it exists — which is what Constitution v2.0 means by *"applications
communicate only through events."*

Every credit keeps the event that caused it, so a score can always be taken
apart into the specific things that earned it. A number nobody can audit is a
number nobody should trust.
"""

from collections import defaultdict

#: What each kind of credited event is worth. Weights are deliberate, not
#: arbitrary: being paid for work outranks being cast for it, which outranks
#: being invited to apply, because each is progressively harder to obtain and
#: therefore progressively better evidence.
WEIGHTS = {
    "hire.completed": 3.0,      # paid work — the strongest signal there is
    "challenge.won": 3.0,       # judged against other entrants
    "ip.purchased": 2.5,
    "ip.licensed": 2.0,
    "asset.licensed": 1.5,
    "project.published": 1.0,
    "role.cast": 1.0,
    "work.registered": 0.5,     # a claim, not corroboration — worth least
}

DEFAULT_WEIGHT = 0.5


class Credit:
    """One thing a creator did, as recorded by whoever witnessed it."""

    __slots__ = ("creator", "kind", "weight", "source", "detail", "event_id", "at")

    def __init__(self, creator, kind, source, detail=None, event_id=None, at=""):
        self.creator = creator
        self.kind = kind
        self.weight = WEIGHTS.get(kind, DEFAULT_WEIGHT)
        self.source = source          # which application witnessed it
        self.detail = detail or {}
        self.event_id = event_id
        self.at = at

    def describe(self):
        what = self.detail.get("production") or self.detail.get("title") or self.kind
        return f"{self.kind} ({self.source}): {what} — {self.weight}"

    def __repr__(self):
        return f"<Credit {self.describe()}>"


class ReputationEngine:
    """Accumulates credits from events. Never invents one.

    Deliberately has no `add_claim` method. If it is not in the event log
    because some application witnessed it, it is not reputation — and adding a
    back door for self-asserted credits would quietly turn this back into a
    résumé.
    """

    def __init__(self, bus=None):
        self._credits = defaultdict(list)
        self._seen_events = set()
        self.bus = bus
        self._subscription = None
        if bus is not None:
            self.listen(bus)

    # -- listening ---------------------------------------------------------

    def listen(self, bus, patterns=None):
        """Subscribe to the credit-worthy events.

        FrameVault decides what counts as reputation; the publishers do not
        know or care that anyone is listening.
        """
        self.bus = bus
        self._subscription = bus.subscribe("*", self._on_event, name="framevault.reputation")
        return self._subscription

    def _on_event(self, event):
        if event.kind not in WEIGHTS:
            return
        creator = event.payload.get("creator")
        if not creator:
            return   # nothing to credit — say nothing rather than guess
        self.record(creator, event.kind, source=event.source,
                    detail=event.payload, event_id=event.id, at=event.occurred_at)

    def replay_from(self, bus, since=0):
        """Catch up on credits that happened before this engine existed.

        The Event Engine keeps a durable log precisely so a listener added
        later is not permanently missing history.
        """
        return bus.replay(self._on_event, since=since)

    # -- recording ---------------------------------------------------------

    def record(self, creator, kind, source, detail=None, event_id=None, at=""):
        """Credit a creator once for one event.

        Idempotent on `event_id`, because a replay after a restart must not
        double a creator's score — and at-least-once delivery makes repeats
        normal rather than exceptional.
        """
        if event_id is not None and event_id in self._seen_events:
            return None
        if event_id is not None:
            self._seen_events.add(event_id)

        credit = Credit(creator, kind, source, detail, event_id, at)
        self._credits[creator].append(credit)
        return credit

    # -- reading -----------------------------------------------------------

    def credits_for(self, creator):
        return list(self._credits.get(creator, ()))

    def score(self, creator):
        return round(sum(c.weight for c in self._credits.get(creator, ())), 2)

    def breakdown(self, creator):
        """The score taken apart. A number nobody can audit is a number nobody
        should trust."""
        by_kind = defaultdict(lambda: {"count": 0, "weight": 0.0})
        for credit in self._credits.get(creator, ()):
            entry = by_kind[credit.kind]
            entry["count"] += 1
            entry["weight"] = round(entry["weight"] + credit.weight, 2)
        return dict(by_kind)

    def sources_for(self, creator):
        """Which applications corroborate this creator.

        Two applications agreeing is stronger evidence than one saying it
        twice — the same independent-source principle CreativeOS's Verification
        Engine uses.
        """
        return sorted({c.source for c in self._credits.get(creator, ())})

    def leaderboard(self, limit=10):
        ranked = [(creator, self.score(creator)) for creator in self._credits]
        ranked.sort(key=lambda pair: (-pair[1], pair[0]))
        return ranked[:limit]

    def profile(self, creator):
        return {
            "creator": creator,
            "score": self.score(creator),
            "credits": len(self._credits.get(creator, ())),
            "sources": self.sources_for(creator),
            "breakdown": self.breakdown(creator),
        }

    def close(self):
        if self.bus is not None and self._subscription is not None:
            self.bus.unsubscribe(self._subscription)
