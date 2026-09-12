"""The Event Engine — publish, subscribe, replay.

This is what replaces applications calling each other. Today FilmCrew posts
directly to FrameVault's `/api/credit` and RightsForge does the same; each app
therefore has to know the others' URLs, service keys, uptime and response
shapes. Constitution v2.0: *"Applications communicate only through events. No
tight coupling."*

With a bus, FilmCrew publishes `hire.completed` and stops caring who listens.
FrameVault subscribes and credits the creator. Adding a third listener — an
analytics engine, a notifier — requires no change to FilmCrew at all, which is
the practical test of whether coupling is really gone.

Order of operations on publish is deliberate: **write to the durable log first,
then dispatch.** A crash after the write loses nothing (subscribers replay); a
crash before it means the event never happened. The other order can announce
something that was never recorded, which is unrecoverable.
"""

from .log import EventLog
from .model import DeliveryFailure


class Subscription:
    def __init__(self, pattern, handler, name):
        self.pattern = pattern
        self.handler = handler
        self.name = name

    def __repr__(self):
        return f"<Subscription {self.name} on {self.pattern!r}>"


class EventBus:
    def __init__(self, conn):
        self.log = EventLog(conn)
        self._subscriptions = []
        self.failures = []

    # -- subscribing --------------------------------------------------------

    def subscribe(self, pattern, handler, name=None):
        """Register `handler(event)` for every event whose kind matches `pattern`.

        `"*"` for everything, `"assertion.*"` for a family, or an exact kind.
        Returns the `Subscription` so it can be cancelled.
        """
        sub = Subscription(pattern, handler, name or getattr(handler, "__name__", "anonymous"))
        self._subscriptions.append(sub)
        return sub

    def unsubscribe(self, subscription):
        if subscription in self._subscriptions:
            self._subscriptions.remove(subscription)

    @property
    def subscriptions(self):
        return tuple(self._subscriptions)

    # -- publishing ---------------------------------------------------------

    def publish(self, space_id, kind, subject_id="", payload=None, source="creativeos"):
        """Record that something happened, then tell everyone listening.

        Returns the stored `Event`. Subscriber errors do not propagate — see
        `dispatch`.
        """
        event = self.log.append(space_id, kind, subject_id, payload, source)
        self.dispatch(event)
        return event

    def dispatch(self, event):
        """Deliver one event to every matching subscriber, in subscription order.

        A subscriber that raises is recorded in `self.failures` and the next one
        still runs. Two reasons: the event is already durably logged, so the
        write it describes has genuinely happened and cannot be un-done by a
        listener's bug; and one broken listener must not be able to take down
        every other listener, or the bus becomes as fragile as the direct HTTP
        calls it replaced.
        """
        delivered = 0
        for sub in list(self._subscriptions):
            if not event.matches(sub.pattern):
                continue
            try:
                sub.handler(event)
                delivered += 1
            except Exception as e:
                self.failures.append(DeliveryFailure(
                    event=event, subscriber=sub.name, error=f"{type(e).__name__}: {e}"
                ))
        return delivered

    # -- replay -------------------------------------------------------------

    def replay(self, handler, since=0, space_id=None, kind=None):
        """Feed historical events to a handler, oldest first.

        This is how an application that was offline catches up, and how one
        added *later* is brought up to date on everything it missed — including
        events published before it was written. Returns the last sequence
        handled, which the caller stores as its cursor.
        """
        cursor = since
        for event in self.log.since(since, space_id=space_id, kind=kind):
            try:
                handler(event)
            except Exception as e:
                self.failures.append(DeliveryFailure(
                    event=event, subscriber=getattr(handler, "__name__", "replay"),
                    error=f"{type(e).__name__}: {e}",
                ))
            cursor = event.sequence
        return cursor

    def history(self, space_id=None, kind=None, since=0):
        return self.log.since(since, space_id=space_id, kind=kind)
