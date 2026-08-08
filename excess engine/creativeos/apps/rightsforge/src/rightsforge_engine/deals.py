"""Listings and deal flow — and the moment a deal becomes a right.

Two deal shapes, one engine, because they are the same transaction wearing
different clothes: somebody acquires rights to a creative work and money moves.

* **asset** — a LUT pack, a music bed. Non-exclusive, instant, many buyers,
  small price. There is no negotiation to model: paying *is* the deal.
* **ip** — a script, a novel, a pilot. Negotiated, usually exclusive, one buyer
  at a time, and it walks `proposed → agreed → paid`.

What makes this an engine rather than a workflow is the last step. Reaching
`paid` does not set a flag on the listing — it **writes a grant into the
ledger**, with a scope and a term. That is the difference between a marketplace
that knows a work is "sold" and one that knows *what was sold, to whom, where,
and until when*.

## Why a listing has no `status`

The obvious model gives a listing `listed | optioned | sold`. It is wrong, and
the way it is wrong is instructive: a status field has no room for *until when*,
so an option locks the work permanently and there is nowhere to record that the
rights came back in March. Availability is therefore **computed** from the
ledger at a given moment, never stored. An option lapsing needs no cleanup job
and no cron — it stops being live because the date passed.

Like FilmCrew, this publishes events and holds no reference to FrameVault or to
any other application. `ip.optioned`, `ip.licensed`, `ip.purchased` and
`asset.licensed` go onto the bus; who listens is not this engine's business.
"""

from creativeos_engine.platform.money import Share, split_pence, validate_split
from .rights import ANY, KINDS, Grant, Ledger, RightsError, Scope, Term

#: The negotiation an IP deal walks. One step at a time, forward only.
IP_FLOW = ("proposed", "agreed", "paid")

#: An asset licence has no negotiation — it is paid or it does not exist.
ASSET_FLOW = ("paid",)

#: Every asset tier grants the same thing: a non-exclusive licence. A tier is a
#: **price band**, not a right — "Personal" and "Commercial" differ in what the
#: buyer is permitted to *do*, which is the application's business rules, not a
#: distinction the rights ledger can enforce. Feeding a tier name straight into
#: the ledger as a deal kind was the first thing the tests caught, and it was
#: the right thing to catch: it would have meant inventing a new kind of right
#: every time somebody named a new pricing tier.
ASSET_RIGHTS_KIND = "license"

#: How long a time-limited grant runs when the caller states no term, expressed
#: in **the caller's own time unit** — the engine never does arithmetic on time
#: beyond comparison, so it cannot know whether `when` counts years or months.
#: `None` is the fallback for any kind not listed.
DEFAULT_TERMS = {"option": 1, "license": 2, "exclusive-license": 2, None: 1}

#: What each deal kind publishes when it completes.
EVENTS = {
    "option": "ip.optioned",
    "license": "ip.licensed",
    "exclusive-license": "ip.licensed",
    "purchase": "ip.purchased",
    "assignment": "ip.purchased",
}


class DealError(Exception):
    """Raised when a deal cannot proceed."""


class Listing:
    """A work offered for sale, and the terms it is offered on."""

    __slots__ = ("id", "listing_type", "seller", "title", "scope", "tiers",
                 "split", "content_hash", "provenance_id")

    def __init__(self, id, listing_type, seller, title, scope=None, tiers=None,
                 split=None, content_hash="", provenance_id=""):
        if listing_type not in ("asset", "ip"):
            raise DealError(f"Unknown listing type '{listing_type}'.")
        self.id = id
        self.listing_type = listing_type
        self.seller = seller
        self.title = title
        #: What is on offer. Defaults to every right, worldwide.
        self.scope = scope or Scope("all")
        #: `{kind_or_tier_name: price_pence}`.
        self.tiers = dict(tiers or {})
        #: Optional `[(payee, percent), ...]`, validated on the way in so an
        #: unpayable split is caught at listing time rather than at payout.
        if split:
            validate_split(split)
        self.split = list(split) if split else None
        self.content_hash = content_hash
        self.provenance_id = provenance_id

    def price_of(self, kind):
        if kind not in self.tiers:
            raise DealError(
                f"'{self.title}' is not offered as '{kind}'. Available: "
                f"{', '.join(sorted(self.tiers)) or 'nothing'}.")
        return self.tiers[kind]

    def describe(self):
        return f"{self.title} ({self.listing_type}) — {self.seller}"

    def __repr__(self):
        return f"<Listing {self.describe()}>"


class Deal:
    """One buyer's transaction against one listing."""

    __slots__ = ("id", "listing_id", "buyer", "kind", "price_pence", "state",
                 "flow", "term", "grant_id", "shares")

    def __init__(self, id, listing_id, buyer, kind, price_pence, flow, term=None):
        self.id = id
        self.listing_id = listing_id
        self.buyer = buyer
        self.kind = kind
        self.price_pence = price_pence
        self.flow = flow
        self.state = flow[0] if len(flow) > 1 else flow[0]
        self.term = term
        self.grant_id = None
        self.shares = []

    @property
    def is_complete(self):
        return self.state == "paid"

    def describe(self):
        return (f"{self.buyer} — {self.kind} — "
                f"£{self.price_pence / 100:,.2f} — {self.state}")

    def __repr__(self):
        return f"<Deal {self.describe()}>"


class RightsForge:
    """Listings, deals, and the ledger they write into."""

    def __init__(self, bus=None, space_id="", source="rightsforge", ledger=None):
        self.bus = bus
        self.space_id = space_id
        self.source = source
        self.ledger = ledger or Ledger()
        self.listings = {}
        self.deals = {}
        self._next = 1

    def _id(self, prefix):
        value = f"{prefix}-{self._next:05d}"
        self._next += 1
        return value

    def _publish(self, kind, subject_id, payload):
        if self.bus is None:
            return None
        return self.bus.publish(self.space_id, kind, subject_id, payload,
                                source=self.source)

    # -- listing -----------------------------------------------------------

    def list_work(self, listing_type, seller, title, tiers, scope=None,
                  split=None, content_hash="", provenance_id=""):
        listing = Listing(self._id("L"), listing_type, seller, title,
                          scope=scope, tiers=tiers, split=split,
                          content_hash=content_hash, provenance_id=provenance_id)
        self.listings[listing.id] = listing
        self._publish("listing.created", listing.id,
                      {"title": title, "type": listing_type, "seller": seller})
        return listing

    def availability(self, listing_id, kind, when, term=None):
        """Whether a given deal could be struck right now, and why not if not.

        Computed from the ledger rather than read off the listing, so a lapsed
        option makes a work available again the moment its term ends — with no
        job to run and nothing to remember to update.
        """
        listing = self._listing(listing_id)
        rights_kind = self._rights_kind(listing, kind)
        exclusive, perpetual = KINDS[rights_kind]
        term = term or Term(when, None if perpetual else when)
        probe = Grant(listing.id, "?", listing.scope, term, kind=rights_kind,
                      exclusive=exclusive)
        conflicts = self.ledger.check(probe)
        return {
            "available": not conflicts,
            "reasons": [c.reason for c in conflicts],
            "held_by": [c.first.holder for c in conflicts],
        }

    # -- dealing -----------------------------------------------------------

    def open_deal(self, listing_id, buyer, kind, when, term=None):
        """Start a deal. Assets complete immediately; IP begins negotiating.

        The availability check happens **here**, at the start, not at payment.
        Letting a buyer negotiate for weeks against a work somebody else already
        holds exclusively is the expensive kind of wrong.
        """
        listing = self._listing(listing_id)
        price = listing.price_of(kind)

        if listing.seller == buyer:
            raise DealError("A seller cannot buy their own listing.")

        term = term or self._default_term(self._rights_kind(listing, kind), when)
        check = self.availability(listing_id, kind, when, term)
        if not check["available"]:
            raise DealError(check["reasons"][0])

        flow = ASSET_FLOW if listing.listing_type == "asset" else IP_FLOW
        deal = Deal(self._id("D"), listing.id, buyer, kind, price, flow, term)
        self.deals[deal.id] = deal

        if listing.listing_type == "asset":
            # Nothing to negotiate: paying is the deal.
            self._complete(listing, deal, when)
        else:
            self._publish("deal.proposed", deal.id,
                          {"listing": listing.id, "buyer": buyer, "kind": kind,
                           "price_pence": price})
        return deal

    def advance(self, deal_id, when):
        """Move an IP deal one step forward. Forward only, one step at a time.

        Both restrictions are deliberate, and they are the same argument
        FilmCrew makes about contracts: a deal that can jump straight to paid
        can skip agreement, and a deal that can go backwards can un-pay
        somebody. Neither is representable here.
        """
        deal = self._deal(deal_id)
        listing = self._listing(deal.listing_id)

        # This also covers asset deals, which complete on creation and so are
        # always "already complete". A separate branch for them would read
        # better and never execute, and unreachable code that looks like a
        # guard is worse than no guard.
        if deal.is_complete:
            raise DealError("This deal is already complete.")

        deal.state = deal.flow[deal.flow.index(deal.state) + 1]
        if deal.is_complete:
            self._complete(listing, deal, when)
        else:
            self._publish("deal.advanced", deal.id, {"state": deal.state})
        return deal

    def _complete(self, listing, deal, when):
        """Payment. The only place a grant is ever written.

        The order matters: the grant is recorded **before** the event is
        published. A listener that reacts to `ip.purchased` by asking the ledger
        who holds the work must not be able to arrive before the answer exists.
        """
        deal.state = "paid"
        grant = self.ledger.record(Grant(
            listing.id, deal.buyer, listing.scope, deal.term,
            kind=self._rights_kind(listing, deal.kind),
            price_pence=deal.price_pence, source=f"deal:{deal.id}"))
        deal.grant_id = grant.grant_id

        if listing.split:
            deal.shares = split_pence(deal.price_pence, listing.split)
        else:
            deal.shares = [Share(listing.seller, 100, deal.price_pence)]

        kind_event = (EVENTS.get(deal.kind, "ip.licensed")
                      if listing.listing_type == "ip" else "asset.licensed")
        self._publish(kind_event, deal.id, {
            "listing": listing.id,
            "title": listing.title,
            "seller": listing.seller,
            "buyer": deal.buyer,
            "kind": deal.kind,
            "amount_pence": deal.price_pence,
            "grant": grant.grant_id,
            "term_ends": deal.term.ends,
            "payees": [{"payee": s.payee, "pence": s.pence} for s in deal.shares],
        })
        return deal

    @staticmethod
    def _rights_kind(listing, kind):
        """Which *right* a deal kind grants.

        For IP the deal kind is the right: an option grants an option. For an
        asset it is a pricing tier, and every tier grants the same non-exclusive
        licence — so the tier name never reaches the ledger.
        """
        if listing.listing_type == "asset":
            return ASSET_RIGHTS_KIND
        if kind not in KINDS:
            raise DealError(
                f"'{kind}' is not a kind of right. Known: {', '.join(sorted(KINDS))}.")
        return kind

    @staticmethod
    def _default_term(kind, when):
        """A term for callers who do not state one.

        The unit is **whatever the caller counts in**. The engine only ever
        compares times with `<`, so `when` can be a year, a month index or a
        date — but that also means a default length is meaningless unless the
        caller's unit is known. `DEFAULT_TERMS` is therefore stated in the
        caller's own units and is the first thing to override in a real
        deployment; a default that silently decides how long somebody holds a
        right should at least be one you can point at.
        """
        _exclusive, perpetual = KINDS[kind]
        if perpetual:
            return Term(when, None)
        return Term(when, when + DEFAULT_TERMS.get(kind, DEFAULT_TERMS[None]))

    # -- reading -----------------------------------------------------------

    def _listing(self, listing_id):
        listing = self.listings.get(listing_id)
        if listing is None:
            raise DealError(f"Unknown listing '{listing_id}'.")
        return listing

    def _deal(self, deal_id):
        deal = self.deals.get(deal_id)
        if deal is None:
            raise DealError(f"Unknown deal '{deal_id}'.")
        return deal

    def deals_for(self, listing_id):
        return [d for d in self.deals.values() if d.listing_id == listing_id]

    def earnings(self, payee):
        """What one payee is owed across every completed deal, in pence."""
        return sum(share.pence
                   for deal in self.deals.values() if deal.is_complete
                   for share in deal.shares if share.payee == payee)

    def summary(self):
        complete = [d for d in self.deals.values() if d.is_complete]
        return {
            "listings": len(self.listings),
            "deals": len(self.deals),
            "completed": len(complete),
            "grants": len(self.ledger.grants),
            "gross_pence": sum(d.price_pence for d in complete),
        }


__all__ = ["RightsForge", "Listing", "Deal", "DealError", "IP_FLOW",
           "ASSET_FLOW", "EVENTS"]
