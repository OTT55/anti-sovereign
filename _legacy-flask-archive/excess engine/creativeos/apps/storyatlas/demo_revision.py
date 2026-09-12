"""Phases 8–11: reconciling people with places, and doing something about it.

    python demo_revision.py

The draft below contains a mistake that is genuinely hard to catch by reading:
a character who dies in one chapter is talking in another, twenty-five years
later. Nothing in the sentence is wrong; the two sentences are wrong *together*,
four hundred words apart.

No model, no network, no API. Every number here is arithmetic over dates the
text supports.
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent / "src"))

from storyatlas_engine import (  # noqa: E402
    Session, analyse, grouping, mindmap, polish, presence,
)
from storyatlas_engine.worklist import next_action, render as render_worklist  # noqa: E402

DRAFT = """CHAPTER ONE

Aldric Vane was born in the year 1102. Dawnhold was founded in the year 1090.

***

He was crowned at the age of thirty. Three years later, the war began.
Mara Sadel died that same year.

***

CHAPTER TWO

In the year 1160, the council gathered at Dawnhold. Mara Sadel spoke against
the treaty. Aldric Vane watched her.

***

Kesh Oru was born in the year 1170. Kesh Oru met Aldric Vane at Emberfall.
"""


def head(n, title):
    print(f"\n{'─' * 72}\n{n}. {title}\n{'─' * 72}")


report = analyse(DRAFT)
reading = report.reading

head(1, "The draft states four dates. The engine solves for the rest.")
for placement in reading.timeline.in_order():
    mark = "·" if placement.source == "stated" else "→"
    year = placement.year if placement.is_dated else "????"
    print(f"  {mark} {str(year):<6} {placement.event.kind:<10} "
          f"{placement.event.subject or '?'}")
print("\n  ·  stated in the draft      →  computed by the engine")
print("\n  \"He was crowned at the age of thirty\" is the interesting one: the")
print("  pronoun has to reach past a castle to find the man it means. Attach it")
print("  to Dawnhold and the coronation has no birth to count from, so it never")
print("  gets dated, so \"three years later\" anchors to the founding instead —")
print("  and a death lands forty-two years early.")

head(2, "Scenes are placed in time — which nothing did before Phase 8")
for date in report.scene_dates:
    print(f"  {date.describe():<34} {date.evidence[:34]}")
print("\n  A scene keeps a span, not a point. Scene 1 covers 1090–1102, so the")
print("  scene that narrates Aldric's birth is not accused of featuring him")
print("  twelve years before it.")

head(3, "Existence intervals — people and places, kept apart")
for existence in presence.existences(reading).values():
    print(f"  {existence.describe()}")
print("\n  \"Dawnhold fell\" and \"Aldric fell\" produce the same event. Untyped,")
print("  a castle acquires a date of death and the engine starts comparing")
print("  people's births against it.")

head(4, "The reconciliation")
if not report.errors:
    print("  (nothing contradicts)")
for violation in report.violations:
    print(f"  [{violation.severity}] {violation.text}")
print("\n  Interval arithmetic: [born, died] ∩ {year} is either empty or it is")
print("  not. Nothing to infer, and the same answer every time.")

head(5, "The cast, era by era — grouping people, not just events")
print(grouping.render_grid(report.grid()))
print("\n  'Alive' is computed from the intervals. 'On the page' is counted from")
print("  the text. The gap between them is the question a writer cannot answer")
print("  by re-reading: who did I forget?")

head(6, "Circles — who keeps turning up with whom")
for circle in grouping.circles(reading):
    print(f"  {circle.describe()}")

head(7, "What to do about it, hardest-working first")
fixes = report.worklist()
print(render_worklist(fixes, limit=3))
chosen = next_action(fixes)
if chosen:
    fix, action = chosen
    print(f"\n  → Start here: {fix.title}")
    print(f"     First option: {action.label}")

head(8, "Interactive revision: decide, preview, see what it breaks")
session = Session(DRAFT)
target = next((f for f in session.issues() if f.severity == "error"), None)
if target is not None:
    option = next((o for o in target.options if o.kind == "annotate"),
                  target.options[0])
    preview = session.preview(target, option)
    print(f"  Chosen: {option.label}")
    print(f"  Result: {preview.describe()}")
    if preview.diff:
        print("\n" + "\n".join("  " + line for line in
                               preview.diff.rstrip().splitlines()[:10]))
    session.apply(target, option)
    print(f"\n  {session.transcript()}")
print("\n  Every decision re-reads the whole draft, because the breakage is")
print("  usually somewhere the edit never touched.")

head(9, "The draft as a mind map, and as an Obsidian vault")
graph = mindmap.build(reading, report)
print(f"  {graph}")
print("  Most connected: " +
      ", ".join(f"{n.label} ({s})" for n, s in graph.central(3)))
print("\n  Vault notes that would be written:")
for filename in sorted(mindmap.vault(reading, report))[:8]:
    print(f"    {filename}")
print("\n  Mermaid (first lines):")
for line in graph.to_mermaid().splitlines()[:6]:
    print(f"    {line}")

head(10, "Local models")
print(f"  {polish.report()}")

print(f"\n{'─' * 72}")
print("No model decided anything above. Every finding is arithmetic the writer")
print("can check by hand, and the same draft always gives the same answer.")
print(f"{'─' * 72}\n")
