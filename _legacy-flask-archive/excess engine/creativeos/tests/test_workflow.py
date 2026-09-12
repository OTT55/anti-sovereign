"""Phase 10 — the Workflow Engine.

Event-driven automation, with the loop protection that makes it safe.
"""

import pytest

from creativeos_engine.workflow import WorkflowEngine


@pytest.fixture
def flow(graph):
    engine = WorkflowEngine(graph.bus)
    yield engine
    engine.close()


def test_a_rule_fires_on_a_matching_event(graph, flow, space, cast):
    seen = []
    flow.add_rule("watch", "assertion.added", lambda e: seen.append(e))
    graph.assert_attribute(cast["kell"].id, "status", "alive")
    assert len(seen) == 1


def test_a_rule_ignores_events_it_does_not_match(graph, flow, space, cast):
    seen = []
    flow.add_rule("watch", "identity.merged", seen.append)
    graph.assert_attribute(cast["kell"].id, "status", "alive")
    assert seen == []


def test_a_condition_can_narrow_a_rule(graph, flow, space, cast):
    seen = []
    flow.add_rule("only-status", "assertion.added", seen.append,
                  condition=lambda e: e.payload.get("predicate") == "status")
    graph.assert_attribute(cast["kell"].id, "rank", "mate")
    graph.assert_attribute(cast["kell"].id, "status", "alive")
    assert len(seen) == 1


def test_a_condition_that_throws_simply_does_not_fire(graph, flow, space, cast):
    def explodes(event):
        raise RuntimeError("bad condition")

    seen = []
    flow.add_rule("broken", "assertion.added", seen.append, condition=explodes)
    graph.assert_attribute(cast["kell"].id, "status", "alive")
    assert seen == []


def test_a_failing_action_is_recorded_not_propagated(graph, flow, space, cast):
    """The event already happened; a rule's bug must not undo the write."""
    def explodes(event):
        raise RuntimeError("bad action")

    flow.add_rule("broken", "assertion.added", explodes)
    graph.assert_attribute(cast["kell"].id, "status", "alive")

    assert graph.state_of(cast["kell"].id) == {"status": "alive"}
    assert len(flow.failures) == 1
    assert "bad action" in flow.failures[0].detail


def test_a_rule_can_write_back_to_the_graph(graph, flow, space, cast):
    """Automation that reacts to a fact by recording another one."""
    def mark_reviewed(event):
        graph.assert_attribute(event.subject_id, "reviewed", "true")

    flow.add_rule("review", "assertion.added", mark_reviewed,
                  condition=lambda e: e.payload.get("predicate") == "status")
    graph.assert_attribute(cast["kell"].id, "status", "alive")

    assert graph.state_of(cast["kell"].id).get("reviewed") == "true"


def test_a_cascade_cannot_run_away(graph, space, cast):
    """A rule whose action triggers itself would loop forever. Depth is bounded
    and the stop is recorded rather than raised."""
    flow = WorkflowEngine(graph.bus, max_depth=3)
    try:
        def echo(event):
            graph.assert_attribute(cast["kell"].id, "echo", "again")

        flow.add_rule("echo", "assertion.added", echo)
        graph.assert_attribute(cast["kell"].id, "start", "here")

        assert len(flow.runs) < 20          # terminated
        assert any(r.status == "depth-limited" for r in flow.runs)
    finally:
        flow.close()


def test_rules_can_be_disabled_and_re_enabled(graph, flow, space, cast):
    seen = []
    flow.add_rule("watch", "assertion.added", seen.append)

    flow.disable("watch")
    graph.assert_attribute(cast["kell"].id, "a", "1")
    assert seen == []

    flow.enable("watch")
    graph.assert_attribute(cast["kell"].id, "b", "2")
    assert len(seen) == 1


def test_a_removed_rule_stops_firing(graph, flow, space, cast):
    seen = []
    flow.add_rule("watch", "assertion.added", seen.append)
    flow.remove_rule("watch")
    graph.assert_attribute(cast["kell"].id, "a", "1")
    assert seen == []


def test_every_run_is_recorded_for_audit(graph, flow, space, cast):
    """Automation you cannot audit is automation you cannot trust."""
    flow.add_rule("watch", "assertion.added", lambda e: None)
    graph.assert_attribute(cast["kell"].id, "status", "alive")

    history = flow.history("watch")
    assert len(history) == 1
    assert history[0].status == "ok"
    assert history[0].at


def test_the_summary_counts_outcomes(graph, flow, space, cast):
    flow.add_rule("ok", "assertion.added", lambda e: None)
    graph.assert_attribute(cast["kell"].id, "status", "alive")
    summary = flow.summary()
    assert summary["rules"] == 1
    assert summary["ok"] == 1
