"""Phase 2 — the Event Engine.

*"Everything emits events. Applications communicate only through events. No
tight coupling. CreativeOS becomes reactive."*
"""

import pytest

from creativeos_engine.domains import STORYATLAS
from creativeos_engine.events import EventBus, EventKind
from creativeos_engine.graph import CreativeGraph, ValidWindow


# -- everything emits events ---------------------------------------------

def test_creating_a_space_emits_an_event(graph):
    u = graph.create_space("Coast", domain="film")
    kinds = [e.kind for e in graph.bus.history()]
    assert EventKind.SPACE_CREATED in kinds
    assert graph.bus.history()[0].subject_id == u.id


def test_every_graph_write_emits_an_event(graph, space, cast):
    """Not a sample — the full set of write operations, each accounted for."""
    kell, harbour = cast["kell"], cast["sera"]
    a = graph.assert_attribute(kell.id, "status", "alive")
    graph.assert_relationship(kell.id, "knows", harbour.id)
    graph.rename_entity(kell.id, "Kell Varo-Ianto")
    graph.retract(a.id, reason="revised")
    graph.declare_entity_type(space.id, "prophecy")

    kinds = [e.kind for e in graph.bus.history()]
    for expected in (
        EventKind.SPACE_CREATED, EventKind.PACK_INSTALLED, EventKind.ENTITY_CREATED,
        EventKind.ASSERTION_ADDED, EventKind.ENTITY_RENAMED,
        EventKind.ASSERTION_RETRACTED, EventKind.TYPE_DECLARED,
    ):
        assert expected in kinds, f"{expected} was never emitted"


def test_event_payload_carries_the_detail(graph, space, cast):
    graph.assert_attribute(cast["kell"].id, "status", "alive",
                           valid=ValidWindow(0, 300), source_kind="manuscript")
    added = [e for e in graph.bus.history() if e.kind == EventKind.ASSERTION_ADDED][-1]
    assert added.payload["predicate"] == "status"
    assert added.payload["object"] == "alive"
    assert added.payload["valid"] == [0, 300]
    assert added.payload["source_kind"] == "manuscript"
    assert added.source == "creativeos.graph"


# -- ordering and durability ---------------------------------------------

def test_sequence_is_monotonic_and_is_the_ordering_authority(graph, space, cast):
    seqs = [e.sequence for e in graph.bus.history()]
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == len(seqs)


def test_events_survive_the_process(tmp_path):
    """The log is on disk, so a crash mid-dispatch loses nothing."""
    db = tmp_path / "space.db"
    with CreativeGraph(str(db)) as g:
        u = g.create_space("Persisted", domain="game", pack=STORYATLAS)
        e = g.create_entity(u.id, "character", "Remembered")
        g.assert_attribute(e.id, "status", "alive")
        before = g.bus.log.count()

    with CreativeGraph(str(db)) as g:
        assert g.bus.log.count() == before
        assert any(ev.kind == EventKind.ENTITY_CREATED for ev in g.bus.history())


# -- subscribing ----------------------------------------------------------

def test_a_subscriber_receives_matching_events(graph, space, cast):
    seen = []
    graph.bus.subscribe(EventKind.ASSERTION_ADDED, seen.append, name="collector")
    graph.assert_attribute(cast["kell"].id, "status", "alive")
    graph.rename_entity(cast["kell"].id, "Someone Else")

    assert len(seen) == 1
    assert seen[0].kind == EventKind.ASSERTION_ADDED


def test_wildcard_and_prefix_subscriptions(graph, space, cast):
    everything, assertions = [], []
    graph.bus.subscribe("*", everything.append, name="all")
    graph.bus.subscribe("assertion.*", assertions.append, name="assertions")

    a = graph.assert_attribute(cast["kell"].id, "status", "alive")
    graph.retract(a.id)
    graph.rename_entity(cast["kell"].id, "Renamed")

    assert len(everything) == 3
    assert [e.kind for e in assertions] == [
        EventKind.ASSERTION_ADDED, EventKind.ASSERTION_RETRACTED,
    ]


def test_unsubscribing_stops_delivery(graph, space, cast):
    seen = []
    sub = graph.bus.subscribe("*", seen.append)
    graph.assert_attribute(cast["kell"].id, "status", "alive")
    graph.bus.unsubscribe(sub)
    graph.assert_attribute(cast["kell"].id, "rank", "mate")
    assert len(seen) == 1


def test_a_broken_subscriber_does_not_break_the_others_or_the_write(graph, space, cast):
    """The write already happened and is logged. One listener's bug must not
    undo it, nor stop the other listeners."""
    good = []

    def explodes(event):
        raise RuntimeError("subscriber is broken")

    graph.bus.subscribe("*", explodes, name="broken")
    graph.bus.subscribe("*", good.append, name="good")

    graph.assert_attribute(cast["kell"].id, "status", "alive")

    assert graph.state_of(cast["kell"].id) == {"status": "alive"}  # write survived
    assert len(good) == 1                                          # other listener ran
    assert len(graph.bus.failures) == 1
    assert "broken" in graph.bus.failures[0].describe()


# -- replay ---------------------------------------------------------------

def test_replay_brings_a_late_subscriber_up_to_date(graph, space, cast):
    """An application added *after* the events happened still catches up. This
    is the difference between decoupled and reactive."""
    graph.assert_attribute(cast["kell"].id, "status", "alive")
    graph.assert_attribute(cast["sera"].id, "status", "alive")

    caught_up = []
    cursor = graph.bus.replay(caught_up.append, kind="assertion.*")

    assert len(caught_up) == 2
    assert cursor == graph.bus.log.latest_sequence()


def test_replay_resumes_from_a_cursor(graph, space, cast):
    graph.assert_attribute(cast["kell"].id, "status", "alive")
    cursor = graph.bus.log.latest_sequence()
    graph.assert_attribute(cast["kell"].id, "rank", "mate")

    later = []
    graph.bus.replay(later.append, since=cursor, kind="assertion.*")
    assert [e.payload["predicate"] for e in later] == ["rank"]


def test_history_of_one_entity(graph, space, cast):
    graph.assert_attribute(cast["kell"].id, "status", "alive")
    graph.assert_attribute(cast["sera"].id, "status", "dead")
    about_kell = graph.bus.log.about(cast["kell"].id)
    assert all(e.subject_id == cast["kell"].id for e in about_kell)


# -- the point: replacing point-to-point HTTP calls -----------------------

def test_events_replace_direct_calls_between_applications(graph, space):
    """Today FilmCrew POSTs to FrameVault's /api/credit and RightsForge does the
    same — each app must know the others' URLs, keys and uptime. v2.0 forbids
    that coupling.

    Here FilmCrew publishes `hire.completed` and knows nothing about who is
    listening. FrameVault credits the creator. An analytics listener is added
    without FilmCrew changing at all — which is the real test of decoupling.
    """
    framevault_credits = []
    analytics = []

    graph.bus.subscribe("hire.completed",
                        lambda e: framevault_credits.append(e.payload["creator"]),
                        name="framevault")

    # FilmCrew publishes. It has no reference to FrameVault whatsoever.
    graph.bus.publish(space.id, "hire.completed", subject_id="ENT-CREATOR",
                      payload={"creator": "@ott", "production": "The Sundered Coast"},
                      source="filmcrew")

    assert framevault_credits == ["@ott"]

    # A third listener appears later. FilmCrew is not modified.
    graph.bus.subscribe("hire.completed", analytics.append, name="analytics")
    graph.bus.publish(space.id, "hire.completed", subject_id="ENT-CREATOR2",
                      payload={"creator": "@sam", "production": "Second Show"},
                      source="filmcrew")

    assert framevault_credits == ["@ott", "@sam"]
    assert len(analytics) == 1


def test_an_application_event_is_logged_with_its_source(graph, space):
    graph.bus.publish(space.id, "asset.licensed", subject_id="ENT-ASSET",
                      payload={"tier": "commercial"}, source="rightsforge")
    event = graph.bus.history(kind="asset.licensed")[0]
    assert event.source == "rightsforge"
    assert event.payload["tier"] == "commercial"


def test_a_bus_can_be_shared_by_two_graphs(tmp_path):
    """Two engines writing into one space still produce one ordered log."""
    db = tmp_path / "shared.db"
    g = CreativeGraph(str(db))
    second = CreativeGraph(store=g.store, bus=g.bus)
    u = g.create_space("Shared", domain="film", pack=STORYATLAS)
    second.create_entity(u.id, "character", "From The Other Engine")

    kinds = [e.kind for e in g.bus.history()]
    assert EventKind.ENTITY_CREATED in kinds
    g.close()
