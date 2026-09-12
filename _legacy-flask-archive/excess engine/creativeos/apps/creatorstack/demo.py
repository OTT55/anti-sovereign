"""What CreatorStack can prove about a competition result.

    python demo.py

The interesting moment is step 2: the challenge closes without anything
running, and a late entry is refused by arithmetic rather than by a status
somebody remembered to change.
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

from creativeos_engine.platform.money import to_pounds  # noqa: E402
from creatorstack_engine import (  # noqa: E402
    AwardError, Ballot, BallotError, CompetitionError, CreatorStack,
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
stack = CreatorStack(bus=bus)

head(1, "A brand posts a brief")
brief = stack.post_challenge(
    "nova-films", "60 seconds of dread",
    brief="One location. No dialogue. Make us not want to look away.",
    prize_pence=500_000, deadline=30, now=0)
print(f"  {brief.describe()}")
print(f"  prize: {to_pounds(brief.prize_pence)}")

head(2, "Entries — and the deadline is arithmetic, not a status")
for who, day in (("ott", 5), ("kestrel", 12), ("nova", 29)):
    entry = stack.submit(brief.id, who, f"{who}'s concept", data=f"{who}.mp4".encode(),
                         now=day)
    print(f"  day {day:>2}  {entry.creator:9} accepted   hash {entry.hash[:16]}…")

try:
    stack.submit(brief.id, "latecomer", "Just finished it", now=31)
except CompetitionError as error:
    print(f"  day 31  latecomer refused — {error}")

print(f"\n  phase on day 30: {stack.phase(brief.id, 30)}")
print(f"  phase on day 31: {stack.phase(brief.id, 31)}")
print("\n  Nothing ran between day 30 and 31. The app stores this deadline and")
print("  never compares it to anything, so that late entry would be accepted.")

head(3, "Who may not enter")
for who, why in (("nova-films", "the sponsor"), ("ott", "already entered")):
    try:
        stack.submit(brief.id, who, "again", now=10)
    except CompetitionError as error:
        print(f"  {who:12} ({why}) — {error}")

head(4, "Voting, with the two checks the app never makes")
entries = stack.entries(brief.id)
ballot = Ballot(brief.id)
for entry in entries:
    try:
        ballot.cast(entry, voter=entry.creator)
    except BallotError as error:
        print(f"  {entry.creator} voting for themselves — refused: {error}")
        break
try:
    ballot.cast(entries[0], voter="nova-films", sponsor=brief.sponsor)
except BallotError as error:
    print(f"  the sponsor voting — refused: {error}")

head(5, "A raw count cannot tell support from coordination")
for i in range(12):                       # a brigade: they voted for nothing else
    ballot.cast(entries[0], voter=f"account{i}")
for i in range(12):                       # real viewers: they voted for two
    ballot.cast(entries[1], voter=f"viewer{i}")
    ballot.cast(entries[2], voter=f"viewer{i}")

for tally in ballot.tally(entries):
    creator = next(e.creator for e in entries if e.id == tally.submission_id)
    print(f"  {creator:9} {tally.votes:>3} votes   "
          f"{tally.single_use:>2} of them voted for nothing else "
          f"({tally.concentration:.0%})")

print("\n  Both leaders have 12. The ranking is NOT reordered — hiding the")
print("  disagreement between 'most votes' and 'most credible votes' would")
print("  throw away the only thing worth showing a judge.")

head(6, "So the engine reports, and a human decides")
for finding in ballot.integrity(entries):
    creator = next(e.creator for e in entries if e.id == finding["submission"])
    print(f"  ⚠ {creator}: {finding['detail']}")
print("\n  Not discounted, not disqualified. Throwing out somebody's votes is")
print("  an accusation, and an engine that makes it silently is one nobody")
print("  can argue with.")

head(7, "Awarding — gated on the phase, not on a flag")
try:
    stack.award(brief.id, [entries[0].id], by="nova-films", now=10)
except AwardError as error:
    print(f"  on day 10 — refused: {error}")
try:
    stack.award(brief.id, [entries[0].id], by="ott", now=31)
except AwardError as error:
    print(f"  by a creator — refused: {error}")

head(8, "The sponsor picks a shortlist, and the pot balances")
award = stack.award(brief.id, [e.id for e in entries], by="nova-films", now=31)
for place, (submission_id, share) in enumerate(zip(award.placings, award.shares), 1):
    creator = next(e.creator for e in entries if e.id == submission_id)
    print(f"  {place}. {creator:9} {to_pounds(share.pence)}")
print(f"\n  total paid: {to_pounds(award.total_pence)}  "
      f"(prize was {to_pounds(brief.prize_pence)})")
print("  Integer pence, largest remainder. A prize fund that does not balance")
print("  is one somebody will ask about.")

head(9, "What was published")
for kind, payload in bus.seen:
    if kind == "challenge.won":
        print(f"  {kind:20} {payload['creator']:9} place {payload['placing']}  "
              f"{to_pounds(payload['amount_pence'])}")
print("\n  Events only. CreatorStack holds no reference to FrameVault — who")
print("  listens is not this engine's business.")

print(f"\n{'─' * 72}")
print(f"{stack.summary(now=31)}")
print("A result you can defend: nothing late was accepted, nobody voted for")
print("themselves, and every penny of the prize is accounted for.")
print(f"{'─' * 72}\n")
