"""Complexity regressions.

A quadratic path does not fail a correctness test — it passes, slowly, and only
becomes visible on real data long after it shipped. These tests assert the
*shape* of the cost curve rather than a wall-clock threshold, so they mean the
same thing on a fast machine and a slow one.
"""


import pytest

from creativeos_engine.graph import CreativeGraph, DomainPack
from creativeos_engine.intelligence import IntelligenceEngine

PACK = DomainPack("bench", entity_types=("thing",), functional_predicates=("status",))


def _ring(n):
    """A ring of n entities, each knowing the next — everything connected,
    nothing pathological."""
    graph = CreativeGraph(":memory:")
    space = graph.create_space("Bench", pack=PACK)
    entities = [graph.create_entity(space.id, "thing", f"E{i}") for i in range(n)]
    for i, entity in enumerate(entities):
        graph.assert_attribute(entity.id, "status", "ok")
        graph.assert_relationship(entity.id, "knows", entities[(i + 1) % n].id)
    return graph, space


def _count_calls(obj, name):
    """Wrap a method so its call count can be asserted. Returns a mutable box.

    Counting beats timing for this. The file's own preamble promised these tests
    assert the *shape* of the cost curve rather than a wall-clock threshold, and
    this one did not keep that promise — it compared two durations, so it
    measured the machine as much as the code. It began failing intermittently
    the day the demo smoke-tests landed (seven subprocesses in the same pytest
    session) and passing again when run alone, which is a test reporting on CPU
    contention rather than on the thing it guards. Best-of-N did not fix it,
    because the contention was sustained rather than a spike.

    A call count is exact, identical on a fast machine and a slow one, and
    describes the regression precisely: the bug was `implications` being
    recomputed *per entity*, so the invariant is that it is computed **once**
    however many entities there are.
    """
    box = {"calls": 0}
    original = getattr(obj, name)

    def counted(*args, **kwargs):
        box["calls"] += 1
        return original(*args, **kwargs)

    setattr(obj, name, counted)
    return box


def test_what_matters_does_not_scale_quadratically():
    """Regression: `impact_of_removing` recomputed every implication in the
    space, and `what_matters` called it once per entity. Measured 4.65s at 400
    entities and rising as the square — about two minutes at 2000, which makes
    `brief()` unusable on a real corpus.

    The invariant, stated exactly: `implications` is computed **once per call**,
    not once per entity. Doubling the entities must not change that number at
    all — which is a stronger claim than "the time roughly doubles", and one
    that means the same thing on every machine.
    """
    graph_a, space_a = _ring(150)
    graph_b, space_b = _ring(300)
    try:
        small_engine = IntelligenceEngine(graph_a)
        large_engine = IntelligenceEngine(graph_b)
        small = _count_calls(small_engine.reasoning, "implications")
        large = _count_calls(large_engine.reasoning, "implications")

        small_engine.what_matters(space_a.id)
        large_engine.what_matters(space_b.id)

        assert small["calls"] == 1, (
            f"implications computed {small['calls']}x for 150 entities — "
            "it should be computed once and shared")
        assert large["calls"] == small["calls"], (
            f"{small['calls']} calls at 150 entities, {large['calls']} at 300 — "
            "the cost is growing with the data, which is the quadratic path "
            "returning")
    finally:
        graph_a.close()
        graph_b.close()


def test_a_single_impact_still_works_without_precomputation():
    """The fix added an optional parameter. Asking for one impact on its own
    must still be correct — it simply pays for the scan itself."""
    graph, space = _ring(20)
    try:
        entity = graph.find_entities(space.id)[0]
        impact = IntelligenceEngine(graph).reasoning.impact_of_removing(entity.id)
        assert impact is not None
        assert impact.direct
    finally:
        graph.close()


def test_precomputed_implications_give_the_same_answer():
    """The optimisation must not change the result — only the cost."""
    graph, space = _ring(20)
    try:
        reasoning = IntelligenceEngine(graph).reasoning
        entity = graph.find_entities(space.id)[0]

        alone = reasoning.impact_of_removing(entity.id)
        shared = reasoning.impact_of_removing(
            entity.id, implications=reasoning.implications(space.id))

        assert alone.summary() == shared.summary()
    finally:
        graph.close()


@pytest.mark.parametrize("n", [50, 200])
def test_a_briefing_completes_on_a_realistic_space(n):
    """The end-to-end path the optimisation exists to protect."""
    graph, space = _ring(n)
    try:
        briefing = IntelligenceEngine(graph).brief(space.id)
        assert briefing.exists["total"] == n
        assert briefing.matters
    finally:
        graph.close()
