"""Domain packs — **not** part of the CreativeOS core.

Constitution v2.0 puts domain vocabulary inside the applications that own it:
StoryAtlas owns characters and scenes, RightsForge owns licenses, FilmCrew owns
call sheets. None of that belongs to CreativeOS.

These packs live here **temporarily**, as reference implementations that prove
the type-registry seam works and give the test suite a real vocabulary to
exercise. Each one moves into its application's own repository as that
application is built — at which point CreativeOS keeps only the registry, never
the words.

Nothing in `creativeos_engine.graph` imports from this package. If that ever
stops being true, the boundary has been broken.
"""

from .storyatlas import STORYATLAS

__all__ = ["STORYATLAS"]
