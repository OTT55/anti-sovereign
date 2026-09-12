"""RightsForge Engine — the domain authority for ownership.

Sits on top of CreativeOS. CreativeOS understands that two records are related;
RightsForge understands that an exclusive UK film licence and an exclusive
worldwide film licence cannot both be sold, and that an option which lapsed in
March stopped being anybody's in March.

Three modules, one idea each:

* `money`  — splits that always reconstruct the total, in integer pence
* `rights` — the ledger: scope × term × exclusivity, and the one collision rule
* `deals`  — listings and deal flow, where a completed deal becomes a grant

Deterministic and self-contained. It publishes events and holds no reference to
FrameVault or to any other application.

    from rightsforge_engine import RightsForge, Scope, Term

    forge = RightsForge()
    script = forge.list_work("ip", "ott", "Nightshift",
                             tiers={"option": 400000, "purchase": 4500000})
    deal = forge.open_deal(script.id, "atlas-films", "option", when=2026)
    forge.advance(deal.id, when=2026)      # proposed -> agreed
    forge.advance(deal.id, when=2026)      # agreed  -> paid, writes the grant

    forge.availability(script.id, "purchase", when=2027)   # blocked by the option
    forge.availability(script.id, "purchase", when=2039)   # option lapsed; free
"""

from .deals import (
    ASSET_FLOW, EVENTS, IP_FLOW, Deal, DealError, Listing, RightsForge,
)
# Money splitting lives in the platform, not here: RightsForge splits
# royalties and CreatorStack splits prizes, and two applications rounding by
# slightly different rules is how a payout quietly comes up short.
from creativeos_engine.platform.money import (
    Share, SplitError, from_pounds, split_pence, to_pounds, total_of,
    validate_split,
)
from .rights import (
    ANY, KINDS, Conflict, Grant, Ledger, RightsError, Scope, Term,
)

__all__ = [
    # deals
    "RightsForge", "Listing", "Deal", "DealError", "IP_FLOW", "ASSET_FLOW",
    "EVENTS",
    # rights
    "Ledger", "Grant", "Scope", "Term", "Conflict", "RightsError", "ANY",
    "KINDS",
    # money
    "Share", "SplitError", "validate_split", "split_pence", "total_of",
    "to_pounds", "from_pounds",
]
