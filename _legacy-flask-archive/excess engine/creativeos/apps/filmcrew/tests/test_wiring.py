"""FilmCrew and FrameVault, wired through events instead of HTTP.

This is the pattern Constitution v2.0 demands and the app in `companies/`
does not yet follow. Today FilmCrew POSTs directly to FrameVault's
`/api/credit`, so it must know FrameVault's URL, its service key, whether it is
running, and what it returns.

Here FilmCrew publishes `hire.completed` and stops. It holds no reference to
FrameVault — no import, no address, no key. FrameVault listens because it
chose to.

The test that proves it is `test_filmcrew_holds_no_reference_to_framevault`:
the wiring is verified by what FilmCrew *cannot see*, not by what it calls.
"""

import sys
from pathlib import Path

import pytest

# FrameVault's engine is a sibling app. Imported only by the *test*, which is
# allowed to see both sides; neither engine imports the other.
_FRAMEVAULT = Path(__file__).resolve().parents[2] / "framevault" / "src"
if _FRAMEVAULT.is_dir():
    sys.path.insert(0, str(_FRAMEVAULT))

from creativeos_engine.graph import CreativeGraph, DomainPack   # noqa: E402
from filmcrew_engine import PipelineError, ProductionEngine     # noqa: E402
from framevault_engine import ReputationEngine                  # noqa: E402

FILMCREW_PACK = DomainPack(
    name="filmcrew",
    entity_types=("production", "crew_role", "contract"),
    functional_predicates=("stage", "state"),
)


@pytest.fixture
def wired():
    """The two applications, sharing only the platform's event bus."""
    graph = CreativeGraph(":memory:")
    space = graph.create_space("Studio", domain="film", pack=FILMCREW_PACK)

    filmcrew = ProductionEngine(bus=graph.bus, space_id=space.id)
    framevault = ReputationEngine(bus=graph.bus)      # listens; never called

    yield graph, filmcrew, framevault
    framevault.close()
    graph.close()


def _run_to_paid(filmcrew, creator="@ott", fee=250_000):
    production = filmcrew.create_production("The Sundered Coast")
    filmcrew.advance_production(production.id)          # drafting -> open
    filmcrew.post_role(production.id, "editor", fee_cents=fee)
    contract = filmcrew.offer(production.id, "editor", creator)
    return production, contract


# -- the magic moment ------------------------------------------------------

def test_paying_a_contract_credits_the_creator(wired):
    _graph, filmcrew, framevault = wired
    production, contract = _run_to_paid(filmcrew)

    assert framevault.score("@ott") == 1.0    # role.cast only, so far

    filmcrew.pay(production.id, contract.id)

    profile = framevault.profile("@ott")
    assert profile["score"] == 4.0            # role.cast 1.0 + hire.completed 3.0
    assert "hire.completed" in profile["breakdown"]


def test_filmcrew_imports_nothing_from_any_sibling_application():
    """The wiring is proved by what FilmCrew cannot see.

    Checked against the parsed **imports**, not the file's text — the module's
    prose explains this boundary and naturally names FrameVault, and a
    text scan would fail on the very comment describing the rule it enforces.
    Only real dependencies count.
    """
    import ast

    import filmcrew_engine
    import filmcrew_engine.production as production_module

    tree = ast.parse(Path(production_module.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")

    siblings = ("framevault", "rightsforge", "creatorstack", "studio", "storyatlas")
    leaked = [name for name in imported
              if any(sibling in name.lower() for sibling in siblings)]
    assert leaked == [], f"FilmCrew imports a sibling application: {leaked}"

    # And it exposes nothing of theirs either.
    assert not hasattr(filmcrew_engine, "ReputationEngine")


def test_a_third_listener_needs_no_change_to_filmcrew(wired):
    """The practical test of decoupling: adding a listener touches nothing."""
    graph, filmcrew, _framevault = wired
    analytics = []
    graph.bus.subscribe("hire.completed", analytics.append, name="analytics")

    production, contract = _run_to_paid(filmcrew)
    filmcrew.pay(production.id, contract.id)

    assert len(analytics) == 1
    assert analytics[0].payload["creator"] == "@ott"


def test_framevault_still_works_with_filmcrew_absent(wired):
    """Nothing about FrameVault depends on FilmCrew existing."""
    graph, _filmcrew, framevault = wired
    graph.bus.publish(graph.find_entities and "", "challenge.won", "",
                      {"creator": "@sam"}, source="creatorstack")
    assert framevault.score("@sam") == 3.0


# -- credit fires on paid, not on hired ------------------------------------

def test_an_offer_alone_does_not_credit_the_work(wired):
    """An offer can be withdrawn and a shoot can collapse."""
    _graph, filmcrew, framevault = wired
    _run_to_paid(filmcrew)
    assert "hire.completed" not in framevault.breakdown("@ott")


def test_every_intermediate_state_stops_short_of_the_credit(wired):
    _graph, filmcrew, framevault = wired
    production, contract = _run_to_paid(filmcrew)

    filmcrew.advance_contract(production.id, contract.id)   # accepted
    filmcrew.advance_contract(production.id, contract.id)   # delivered
    assert "hire.completed" not in framevault.breakdown("@ott")

    filmcrew.advance_contract(production.id, contract.id)   # paid
    assert "hire.completed" in framevault.breakdown("@ott")


# -- the pipeline refuses to skip ------------------------------------------

def test_a_contract_cannot_skip_to_paid(wired):
    """Skipping is how a creator gets credited for work nobody delivered."""
    _graph, filmcrew, _framevault = wired
    production, contract = _run_to_paid(filmcrew)
    assert contract.state == "offered"

    filmcrew.advance_contract(production.id, contract.id)
    assert contract.state == "accepted"      # one step, not four


def test_a_paid_contract_cannot_advance_again(wired):
    _graph, filmcrew, _framevault = wired
    production, contract = _run_to_paid(filmcrew)
    filmcrew.pay(production.id, contract.id)

    with pytest.raises(PipelineError):
        filmcrew.advance_contract(production.id, contract.id)


def test_roles_cannot_be_posted_to_a_draft(wired):
    _graph, filmcrew, _framevault = wired
    production = filmcrew.create_production("Unstarted")
    with pytest.raises(PipelineError):
        filmcrew.post_role(production.id, "editor")


def test_a_filled_role_cannot_be_offered_twice(wired):
    _graph, filmcrew, _framevault = wired
    production, _contract = _run_to_paid(filmcrew)
    with pytest.raises(PipelineError):
        filmcrew.offer(production.id, "editor", "@someone-else")


# -- the credit is auditable -----------------------------------------------

def test_a_credit_keeps_the_event_that_caused_it(wired):
    """A number nobody can audit is a number nobody should trust."""
    _graph, filmcrew, framevault = wired
    production, contract = _run_to_paid(filmcrew)
    filmcrew.pay(production.id, contract.id)

    credit = next(c for c in framevault.credits_for("@ott")
                  if c.kind == "hire.completed")
    assert credit.source == "filmcrew"
    assert credit.event_id
    assert credit.detail["production"] == "The Sundered Coast"


def test_replaying_the_log_does_not_double_a_score(wired):
    """At-least-once delivery makes repeats normal, not exceptional."""
    graph, filmcrew, framevault = wired
    production, contract = _run_to_paid(filmcrew)
    filmcrew.pay(production.id, contract.id)
    before = framevault.score("@ott")

    framevault.replay_from(graph.bus, since=0)
    assert framevault.score("@ott") == before


def test_a_listener_added_late_catches_up(wired):
    """The durable log exists so a listener added later is not permanently
    missing history."""
    graph, filmcrew, _framevault = wired
    production, contract = _run_to_paid(filmcrew)
    filmcrew.pay(production.id, contract.id)

    latecomer = ReputationEngine()
    latecomer.replay_from(graph.bus, since=0)
    assert latecomer.score("@ott") == 4.0


def test_payroll_counts_only_what_was_actually_paid(wired):
    _graph, filmcrew, _framevault = wired
    production, contract = _run_to_paid(filmcrew, fee=250_000)
    assert filmcrew.payroll_cents(production.id) == 0

    filmcrew.pay(production.id, contract.id)
    assert filmcrew.payroll_cents(production.id) == 250_000
