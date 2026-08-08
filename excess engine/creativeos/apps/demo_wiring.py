"""FilmCrew and FrameVault, talking without knowing about each other.

    python demo_wiring.py

Real engines, real event log, no HTTP and no network. Today the apps in
`companies/` do this with a direct POST from FilmCrew to FrameVault's
`/api/credit`, which means FilmCrew must know FrameVault's address, its service
key, and whether it is switched on. Here neither app has heard of the other.
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "filmcrew" / "src"))
sys.path.insert(0, str(_HERE / "framevault" / "src"))
sys.path.insert(0, str(_HERE.parent / "src"))

from creativeos_engine.graph import CreativeGraph, DomainPack   # noqa: E402
from filmcrew_engine import ProductionEngine                    # noqa: E402
from framevault_engine import ReputationEngine                  # noqa: E402


def head(n, title):
    print(f"\n{'─' * 70}\n{n}. {title}\n{'─' * 70}")


graph = CreativeGraph(":memory:")
space = graph.create_space("OTT Studio", domain="film", pack=DomainPack(
    name="filmcrew", entity_types=("production", "crew_role", "contract")))

filmcrew = ProductionEngine(bus=graph.bus, space_id=space.id)
framevault = ReputationEngine(bus=graph.bus)

head(1, "Two applications, one shared bus")
print("  FilmCrew   — publishes what happens in a production")
print("  FrameVault — listens for anything worth crediting")
print("\n  Neither imports the other. FilmCrew has no URL, no key, no reference.")

head(2, "A production is set up")
production = filmcrew.create_production("The Sundered Coast")
filmcrew.advance_production(production.id)
filmcrew.post_role(production.id, "editor", fee_cents=250_000)
filmcrew.post_role(production.id, "composer", fee_cents=180_000)
print(f"  {production.describe()}")
print(f"  roles posted: {', '.join(production.roles)}")

head(3, "Someone is cast — but not yet credited for the work")
contract = filmcrew.offer(production.id, "editor", "@ott")
print(f"  {contract.describe()}")
print(f"  @ott's reputation: {framevault.score('@ott')}  (being cast counts a little)")
print("  An offer can be withdrawn and a shoot can collapse, so the work")
print("  itself is not credited yet.")

head(4, "The contract runs its course")
for _ in range(3):
    state = filmcrew.advance_contract(production.id, contract.id)
    marker = "  <-- money changes hands" if state == "paid" else ""
    print(f"  contract is now {state}{marker}")

head(5, "FrameVault credited the creator — without being called")
profile = framevault.profile("@ott")
print(f"  score   : {profile['score']}")
print(f"  credits : {profile['credits']}")
print(f"  sources : {', '.join(profile['sources'])}")
print("\n  breakdown:")
for kind, entry in sorted(profile["breakdown"].items()):
    print(f"    {kind:<18} x{entry['count']}  weight {entry['weight']}")

head(6, "Every credit can be traced to the event that caused it")
for credit in framevault.credits_for("@ott"):
    print(f"  {credit.kind:<16} from {credit.source:<10} event {credit.event_id}")
print("\n  A score nobody can take apart is a score nobody should trust.")

head(7, "A third listener, added now, needs no change to FilmCrew")
analytics = []
graph.bus.subscribe("hire.completed", analytics.append, name="analytics")

second = filmcrew.offer(production.id, "composer", "@sam")
filmcrew.pay(production.id, second.id)
print(f"  analytics saw {len(analytics)} hire(s); @sam scored {framevault.score('@sam')}")
print("  FilmCrew was not modified, restarted, or told anything.")

head(8, "The whole conversation, in order")
for event in graph.bus.history():
    print(f"  {event.describe()}")

print(f"\n{'─' * 70}")
print(f"Payroll actually paid: {filmcrew.payroll_cents(production.id):,} cents")
print("No HTTP. No service keys. No app knows another app's address.")
print(f"{'─' * 70}\n")

graph.close()
