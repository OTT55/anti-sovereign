"""StoryAtlas Engine — the domain authority for narrative comprehension.

Sits on top of CreativeOS. CreativeOS understands entities, relationships and
time; StoryAtlas understands that this entity is a character, that this verb is
a death, and that "three years later" resolves to 1135.

Deterministic throughout. No API calls and no model anywhere in the reasoning:
every conclusion is arithmetic over dates the text supports, so the same draft
always gives the same reading and every finding can be checked by hand. The one
optional seam is `polish`, which is off by default, may rephrase a sentence and
is forbidden from changing a fact.

    from storyatlas_engine import analyse, Session

    report = analyse(draft)
    print(report.render())              # what the draft says, and what breaks
    print(report.worklist()[0].title)   # what to fix first, by leverage

    session = Session(draft)            # interactive revision
    fix = session.issues()[0]
    print(session.preview(fix, fix.options[0], value=1150).render())
"""

from . import canon, grouping, mindmap, polish, presence, structure, worklist
from .grouping import cast_at, circles, eras, generations, render_grid, timeline_grid
from .intelligence import Report, analyse
from .mindmap import build as mindmap_of
from .mindmap import vault, write_vault
from .presence import (
    appearances, character_lifespans, date_scenes, existences, itinerary,
    occupancy, reconcile,
)
from .reading import Question, Reading, read
from .revise import Decision, Preview, Session
from .worklist import Action, Fix

__all__ = [
    # reading and reporting
    "read", "analyse", "Reading", "Report", "Question",
    # reconciling people, places and time
    "reconcile", "existences", "character_lifespans", "date_scenes",
    "appearances", "itinerary", "occupancy",
    # grouping the cast inside the timeline
    "eras", "cast_at", "circles", "generations", "timeline_grid", "render_grid",
    # acting on it
    "Action", "Fix", "Session", "Preview", "Decision",
    # seeing it
    "mindmap_of", "vault", "write_vault",
    # modules
    "canon", "grouping", "mindmap", "polish", "presence", "structure", "worklist",
]
