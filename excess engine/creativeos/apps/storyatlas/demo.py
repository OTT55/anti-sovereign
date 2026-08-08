"""What the StoryAtlas engine understands from a draft.

    python demo.py

Real engine, real output, no model calls and no network. The draft below states
exactly two dates; everything else is solved for.
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent / "src"))

from storyatlas_engine import analyse, read  # noqa: E402

DRAFT = """
Chancellor Aldric Vane was born in the year 1102 in the city of Dawnhold.
He was crowned at the age of thirty.
Three years later, the Meridian War began.
Mara Sadel died that same year at Dawnhold.
Aldric was killed by Tobin Reyes two years later.
A decade later, Tobin Reyes founded the Order of the Broken Crown.
In 1155, Mara Sadel signed the Dawnhold Accord.
"""


def head(n, title):
    print(f"\n{'─' * 70}\n{n}. {title}\n{'─' * 70}")


reading = read(DRAFT)

head(1, "What it found")
print("Names:", ", ".join(reading.names))
s = reading.summary()
print(f"\n{s['events']} events from {s['sentences']} sentences.")
print(f"Dates stated in the draft: 2.  Dates the engine solved for: {s['computed_dates']}.")

head(2, "The timeline it worked out")
for p in reading.timeline.in_order():
    mark = "·" if p.source == "stated" else "→"
    year = p.year if p.is_dated else "????"
    print(f"  {mark} {str(year):<6} {p.event.kind:<10} {p.event.subject or '?'}")
print("\n  ·  stated in the draft      →  computed by the engine")

head(3, "Who died, and when")
for who, when in reading.deaths():
    print(f"  {who} — {when}")

head(4, "Lifespans, derived")
for name, (born, died) in sorted(reading.lifespans().items()):
    if born or died:
        print(f"  {name:<26} {born or '?'} – {died or '?'}")

head(5, "Grouped by what happened")
for kind, placements in sorted(reading.by_kind().items()):
    who = ", ".join(p.event.subject or "?" for p in placements)
    print(f"  {kind:<12} {len(placements)}  ({who})")

head(6, "Grouped by person")
for name, placements in sorted(reading.by_person().items()):
    trail = " → ".join(f"{p.event.kind} {p.year or '?'}" for p in placements)
    print(f"  {name}\n      {trail}")

head(7, "What it will not assume — it asks instead")
if not reading.questions:
    print("  (nothing uncertain)")
for q in reading.questions:
    print(f"  [{q.kind}] {q.text}")
    print(f"        “{q.evidence.strip()[:62]}”")
    if q.options:
        print(f"        options: {', '.join(q.options[:3])}")

head(8, "Scenes, relationships and continuity")

report = analyse(DRAFT)

print("Scenes:")
for scene in report.reading.scenes:
    print(f"  {scene.describe()}")

if report.reading.relations:
    print("\nRelationships (→ = inferred inverse):")
    for rel in report.reading.relations:
        print(f"  {rel.describe()}")

print("\nCharacter threads:")
for thread in report.threads:
    print(f"  {thread.describe()}")

if report.violations:
    print("\nCanon violations:")
    for v in report.violations:
        print(f"  {v.describe()}")

if report.observations:
    print("\nShape of the draft:")
    for o in report.observations:
        print(f"  {o.text}")

print(f"\n{'─' * 70}")
print("Deterministic: no API calls, no model, no training.")
print("Same draft in, same reading out, every time.")
print(f"{'─' * 70}\n")
