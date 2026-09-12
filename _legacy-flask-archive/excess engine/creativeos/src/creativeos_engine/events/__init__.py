"""The Event Engine — *"Everything emits events. No tight coupling."*

Phase 2 of `BUILD_PLAN.md`. Durable append-only log plus publish/subscribe and
replay. Deterministic, in-process, no network and no model calls — transport
across processes is a later concern layered on the same log.
"""

from .bus import EventBus, Subscription
from .log import EventLog
from .model import DeliveryFailure, Event, EventKind

__all__ = ["EventBus", "EventLog", "Event", "EventKind", "Subscription", "DeliveryFailure"]
