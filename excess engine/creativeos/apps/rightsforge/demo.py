"""What RightsForge can prove about who owns what.

    python demo.py

The interesting moment is step 6: an option lapses and the work becomes
available again, with nothing having run.
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent / "src"))

# The shared CreativeOS platform, found by searching upward rather than by
# counting parents — the same rule the conftest uses. A demo is a standalone
# script and gets none of pytest's path setup, so it has to do this itself:
# moving `money` up into the platform broke both demos while every test still
# passed, because only the tests had the platform on their path.
for _parent in Path(__file__).resolve().parents:
    if (_parent / "src" / "creativeos_engine").is_dir():
        sys.path.insert(0, str(_parent / "src"))
        break

from rightsforge_engine import (  # noqa: E402
    DealError, RightsForge, Scope, SplitError, Term, to_pounds, validate_split,
)


class Bus:
    def __init__(self):
        self.seen = []

    def publish(self, space_id, kind, subject_id, payload, source=""):
        self.seen.append((kind, payload))
        return len(self.seen)


def head(n, title):
    print(f"\n{'─' * 72}\n{n}. {title}\n{'─' * 72}")


bus = Bus()
forge = RightsForge(bus=bus)

head(1, "Two listings, two completely different deal shapes")
luts = forge.list_work(
    "asset", "ott", "“Umber” — warm cinematic LUT pack",
    tiers={"personal": 2_900, "commercial": 8_900, "studio": 24_000},
    split=[("OTT", 70), ("Kojo Mensah", 30)])
script = forge.list_work(
    "ip", "ott", "“Nightshift” — feature screenplay", scope=Scope("film"),
    tiers={"option": 400_000, "license": 1_800_000, "purchase": 4_500_000})
print(f"  asset: {luts.describe()}")
print(f"  ip   : {script.describe()}")
print("\n  Same engine. An asset is non-exclusive and instant; IP is exclusive")
print("  and negotiated. Only the deal shape differs.")

head(2, "An asset sells to everyone, and the split always adds up")
for buyer in ("nova", "kestrel", "atlas-films"):
    deal = forge.open_deal(luts.id, buyer, "commercial", when=2026)
    parts = "  ·  ".join(s.describe() for s in deal.shares)
    print(f"  {buyer:12} {to_pounds(deal.price_pence)}   →  {parts}")
print(f"\n  OTT has earned {to_pounds(forge.earnings('OTT'))}, "
      f"Kojo {to_pounds(forge.earnings('Kojo Mensah'))}.")
print("  Every payout reconstructs the price exactly — largest-remainder over")
print("  integer pence, never floats, never a rounded share that loses a penny.")

head(3, "A split that does not reach 100% is refused when the work is listed")
try:
    validate_split([("OTT", 70), ("Kojo Mensah", 27)])
except SplitError as error:
    print(f"  refused — {error}")
print("\n  The app never checks. A 97% split silently decides who absorbs the 3%.")

head(4, "An IP deal negotiates")
# The term is stated rather than defaulted: the engine only ever compares times,
# so it cannot know whether `when` counts years or months, and a default that
# quietly decides how long somebody holds a right is worth stating out loud.
deal = forge.open_deal(script.id, "atlas-films", "option", when=2026,
                       term=Term(2026, 2036))
print(f"  {deal.describe()}")
for _ in range(2):
    forge.advance(deal.id, 2026)
    print(f"  {deal.describe()}")
print("\n  One step at a time, forward only. A deal that can jump to paid can")
print("  skip agreement; one that can go backwards can un-pay somebody.")

head(5, "Payment writes a GRANT, not a flag")
grant = forge.ledger.for_work(script.id)[0]
print(f"  {grant.describe()}")
print(f"  grant id: {grant.grant_id}")
print("\n  What was sold, to whom, over what, and until when. A `status` column")
print("  can hold none of that.")

head(6, "So the option blocks a purchase — and then stops")
for year in (2030, 2036, 2037):
    check = forge.availability(script.id, "purchase", when=year)
    if check["available"]:
        print(f"  {year}: available")
    else:
        print(f"  {year}: blocked — {check['reasons'][0]}")
print("\n  Nothing ran between 2036 and 2037. No cron job, no cleanup, no")
print("  status to remember to reset. The term ended and the grant stopped")
print("  being live. That is the whole argument for modelling a term.")

head(7, "Territory and medium are separate axes")
uk = forge.list_work("ip", "ott", "“Harbour” — novel", scope=Scope("film", "uk"),
                     tiers={"purchase": 900_000})
france = forge.list_work("ip", "ott", "“Harbour” — novel (FR)",
                         scope=Scope("film", "france"), tiers={"purchase": 500_000})
for listing, buyer in ((uk, "atlas-films"), (france, "gaumont")):
    d = forge.open_deal(listing.id, buyer, "purchase", when=2026)
    forge.advance(d.id, 2026)
    forge.advance(d.id, 2026)
print("  Film rights sold in the UK and in France, on the same day, to different")
print("  buyers — no conflict. A single sold/not-sold flag cannot express that,")
print("  and territory-by-territory is how the business actually works.")

head(8, "What was published")
for kind, payload in bus.seen:
    if kind.startswith(("ip.", "asset.")):
        print(f"  {kind:16} {payload['title'][:40]:42} {to_pounds(payload['amount_pence'])}")
print("\n  Events only. RightsForge holds no reference to FrameVault — who")
print("  listens is not this engine's business.")

head(9, "An exclusive right cannot be sold twice")
try:
    forge.open_deal(uk.id, "rival-pictures", "purchase", when=2027)
except DealError as error:
    print(f"  refused — {error}")
print("\n  Refused when the deal OPENS, not at payment. Letting somebody")
print("  negotiate for weeks against a work they can never have is the")
print("  expensive kind of wrong.")

print(f"\n{'─' * 72}")
print(f"{forge.summary()}")
print("Ownership is computed, never stored. Ask again in a different year and")
print("you get a different — and correct — answer.")
print(f"{'─' * 72}\n")
