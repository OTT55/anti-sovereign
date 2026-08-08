"""Listings and deal flow — and the moment a deal becomes a right."""

import pytest

from rightsforge_engine import DealError, RightsForge, Scope, Term


class FakeBus:
    """Records what was published. Real enough to assert ordering against."""

    def __init__(self):
        self.published = []

    def publish(self, space_id, kind, subject_id, payload, source=""):
        self.published.append({"kind": kind, "subject": subject_id,
                               "payload": payload, "source": source})
        return len(self.published)

    def kinds(self):
        return [e["kind"] for e in self.published]


@pytest.fixture
def forge():
    return RightsForge(bus=FakeBus())


@pytest.fixture
def script(forge):
    return forge.list_work("ip", "ott", "Nightshift",
                           tiers={"option": 400_000, "license": 1_800_000,
                                  "purchase": 4_500_000},
                           scope=Scope("film"))


@pytest.fixture
def luts(forge):
    return forge.list_work("asset", "ott", "Umber LUT pack",
                           tiers={"personal": 2_900, "commercial": 8_900},
                           split=[("OTT", 70), ("Kojo Mensah", 30)])


# -- assets: paying is the deal ---------------------------------------------

def test_an_asset_licence_completes_immediately(forge, luts):
    deal = forge.open_deal(luts.id, "buyer", "commercial", when=2026)
    assert deal.is_complete
    assert forge.bus.kinds()[-1] == "asset.licensed"


def test_an_asset_sells_to_many_buyers(forge, luts):
    """Non-exclusive by nature, which is the whole difference from IP."""
    for i in range(20):
        forge.open_deal(luts.id, f"buyer{i}", "personal", when=2026)
    assert forge.summary()["completed"] == 20


def test_an_asset_deal_cannot_be_advanced(forge, luts):
    """It completed on purchase, so there is nowhere to advance it to."""
    deal = forge.open_deal(luts.id, "buyer", "personal", when=2026)
    with pytest.raises(DealError, match="already complete"):
        forge.advance(deal.id, when=2026)


def test_a_split_is_applied_at_payment(forge, luts):
    deal = forge.open_deal(luts.id, "buyer", "commercial", when=2026)
    assert {s.payee: s.pence for s in deal.shares} == {"OTT": 6230, "Kojo Mensah": 2670}
    assert sum(s.pence for s in deal.shares) == 8900


def test_without_a_split_the_seller_takes_everything(forge, script):
    deal = forge.open_deal(script.id, "atlas", "purchase", when=2026)
    forge.advance(deal.id, 2026)
    forge.advance(deal.id, 2026)
    assert [(s.payee, s.pence) for s in deal.shares] == [("ott", 4_500_000)]


def test_earnings_accumulate_across_deals(forge, luts):
    for i in range(3):
        forge.open_deal(luts.id, f"buyer{i}", "commercial", when=2026)
    assert forge.earnings("OTT") == 6230 * 3


def test_an_unpayable_split_is_refused_at_listing_time(forge):
    """Caught when the work is listed, not at payout when somebody is short."""
    with pytest.raises(Exception, match="97%"):
        forge.list_work("asset", "ott", "Broken", tiers={"a": 100},
                        split=[("a", 70), ("b", 27)])


# -- IP: a negotiation ------------------------------------------------------

def test_an_ip_deal_walks_the_flow(forge, script):
    deal = forge.open_deal(script.id, "atlas", "option", when=2026)
    assert deal.state == "proposed"
    assert forge.advance(deal.id, 2026).state == "agreed"
    assert forge.advance(deal.id, 2026).state == "paid"


def test_a_deal_cannot_skip_a_step(forge, script):
    """A deal that can jump to paid can skip agreement."""
    deal = forge.open_deal(script.id, "atlas", "option", when=2026)
    forge.advance(deal.id, 2026)
    forge.advance(deal.id, 2026)
    with pytest.raises(DealError, match="already complete"):
        forge.advance(deal.id, 2026)


def test_only_completion_publishes_the_deal_event(forge, script):
    deal = forge.open_deal(script.id, "atlas", "option", when=2026)
    assert "ip.optioned" not in forge.bus.kinds()
    forge.advance(deal.id, 2026)
    assert "ip.optioned" not in forge.bus.kinds()
    forge.advance(deal.id, 2026)
    assert "ip.optioned" in forge.bus.kinds()


def test_each_deal_kind_publishes_its_own_event(forge, script):
    deal = forge.open_deal(script.id, "atlas", "purchase", when=2026)
    forge.advance(deal.id, 2026)
    forge.advance(deal.id, 2026)
    assert "ip.purchased" in forge.bus.kinds()


def test_a_seller_cannot_buy_their_own_listing(forge, script):
    with pytest.raises(DealError, match="own listing"):
        forge.open_deal(script.id, "ott", "option", when=2026)


def test_a_kind_that_is_not_offered_is_refused(forge, script):
    with pytest.raises(DealError, match="not offered"):
        forge.open_deal(script.id, "atlas", "assignment", when=2026)


# -- the ledger is what makes it an engine ----------------------------------

def test_payment_writes_a_grant_with_a_term(forge, script):
    """Not a flag on the listing — what was sold, to whom, and until when."""
    deal = forge.open_deal(script.id, "atlas", "option", when=2026)
    forge.advance(deal.id, 2026)
    forge.advance(deal.id, 2026)
    assert deal.grant_id
    grant = forge.ledger.for_work(script.id)[0]
    assert grant.holder == "atlas"
    assert grant.term.ends == 2027          # a bounded option, not forever


def _optioned(forge, script, holder="atlas", term=None):
    """An option taken all the way to paid, with an explicit term.

    Explicit because the engine's default term is expressed in the caller's own
    time unit and it cannot know whether `when` counts years or months — a test
    that leans on that default is testing the default, not the behaviour.
    """
    deal = forge.open_deal(script.id, holder, "option", when=2026,
                           term=term or Term(2026, 2036))
    forge.advance(deal.id, 2026)
    forge.advance(deal.id, 2026)
    return deal


def test_an_option_blocks_a_purchase_while_it_runs(forge, script):
    _optioned(forge, script)
    assert not forge.availability(script.id, "purchase", when=2030)["available"]


def test_a_lapsed_option_makes_the_work_available_again(forge, script):
    """The behaviour a `status` column cannot produce. Nothing runs, no job
    cleans up — the date simply passes."""
    _optioned(forge, script)
    assert not forge.availability(script.id, "purchase", when=2036)["available"]
    assert forge.availability(script.id, "purchase", when=2037)["available"]


def test_availability_says_who_is_blocking(forge, script):
    _optioned(forge, script, holder="atlas-films")
    check = forge.availability(script.id, "purchase", when=2030)
    assert check["held_by"] == ["atlas-films"]
    assert "atlas-films" in check["reasons"][0]


def test_availability_is_checked_when_the_deal_opens_not_at_payment(forge, script):
    """Letting a buyer negotiate for weeks against a work somebody else already
    holds exclusively is the expensive kind of wrong."""
    first = forge.open_deal(script.id, "atlas", "purchase", when=2026)
    forge.advance(first.id, 2026)
    forge.advance(first.id, 2026)
    with pytest.raises(DealError, match="exclusive"):
        forge.open_deal(script.id, "rival", "option", when=2027)


def test_the_grant_exists_before_the_event_is_published(forge, script):
    """A listener reacting to `ip.purchased` must not be able to ask the ledger
    who holds the work and arrive before the answer exists."""
    deal = forge.open_deal(script.id, "atlas", "purchase", when=2026)
    forge.advance(deal.id, 2026)

    seen = {}
    original = forge.bus.publish

    def spy(space_id, kind, subject_id, payload, source=""):
        if kind == "ip.purchased":
            seen["holder"] = forge.ledger.holder_of(script.id, Scope("film"), 2026)
        return original(space_id, kind, subject_id, payload, source)

    forge.bus.publish = spy
    forge.advance(deal.id, 2026)
    assert seen["holder"] is not None
    assert seen["holder"].holder == "atlas"


def test_the_completion_event_carries_the_payout_breakdown(forge, luts):
    forge.open_deal(luts.id, "buyer", "commercial", when=2026)
    payload = forge.bus.published[-1]["payload"]
    assert payload["amount_pence"] == 8900
    assert sum(p["pence"] for p in payload["payees"]) == 8900


# -- boundaries -------------------------------------------------------------

def test_the_engine_runs_without_a_bus(script):
    """Publishing is optional; the engine is not a messaging client."""
    forge = RightsForge()
    listing = forge.list_work("asset", "ott", "Thing", tiers={"a": 100})
    assert forge.open_deal(listing.id, "buyer", "a", when=2026).is_complete


def test_unknown_listings_and_deals_are_refused(forge):
    with pytest.raises(DealError, match="Unknown listing"):
        forge.open_deal("nope", "buyer", "a", when=2026)
    with pytest.raises(DealError, match="Unknown deal"):
        forge.advance("nope", when=2026)


def test_an_unknown_listing_type_is_refused(forge):
    with pytest.raises(DealError, match="Unknown listing type"):
        forge.list_work("merch", "ott", "T-shirt", tiers={"a": 100})


def test_the_engine_imports_nothing_from_a_sibling_application():
    """Vertical dependencies are allowed; horizontal ones are not. Parsed as
    imports rather than scanned as text — the docstrings name FrameVault and
    StoryAtlas while explaining the boundary."""
    import ast
    import pathlib

    package = pathlib.Path(__file__).resolve().parents[1] / "src" / "rightsforge_engine"
    siblings = ("storyatlas_engine", "framevault_engine", "filmcrew_engine",
                "creatorstack_engine", "studio_engine")
    for module in package.glob("*.py"):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                assert not name.startswith(siblings), f"{module.name} imports {name}"


def test_a_deal_is_deterministic(forge, luts):
    first = forge.open_deal(luts.id, "a", "commercial", when=2026)
    second = forge.open_deal(luts.id, "b", "commercial", when=2026)
    assert [s.pence for s in first.shares] == [s.pence for s in second.shares]
