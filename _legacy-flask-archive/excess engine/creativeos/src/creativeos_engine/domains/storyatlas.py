"""StoryAtlas's vocabulary — the domain authority for narrative comprehension.

Every name in this file was previously an `EntityKind` member inside the
CreativeOS core. Under Constitution v1.0 that was right: CreativeOS *was* the
creative-intelligence engine. Under v2.0 it is precisely the mixing the
constitution forbids — *"StoryAtlas understands kingdoms. CreativeOS
understands entities."* — so the words moved here and the core kept only the
mechanism.

This pack is what StoryAtlas would hand to CreativeOS on `create_space()`.
"""

from ..graph.types import DomainPack

#: The narrative node vocabulary. `other` plus an entity's free-text `subkind`
#: means an unforeseen creative concept never blocks on a code change.
STORYATLAS_ENTITY_TYPES = (
    "idea", "project", "story", "act", "scene", "dialogue",
    "character", "location", "country", "culture", "organization",
    "artifact", "vehicle", "magic_system", "technology",
    "event", "timeline", "asset", "music", "creator", "other",
)

#: Predicates that may hold at most one value at any single moment, so only
#: these can contradict each other. A character has one `status` at a time but
#: may well have several `trait`s.
#:
#: Getting this wrong in the permissive direction costs a missed conflict;
#: getting it wrong in the strict direction cries wolf on a character who is
#: simply allowed to be both brave and reckless. A short, obviously
#: single-valued list keeps false positives near zero.
#:
#: Note this is domain judgement, not universal truth — `species` is
#: single-valued in most fiction and explicitly not in some. Only the
#: application can make that call, which is exactly why the core does not.
STORYATLAS_FUNCTIONAL_PREDICATES = (
    "status", "species", "gender", "age", "occupation", "title",
    "allegiance", "location", "rank", "alive",
)

STORYATLAS = DomainPack(
    name="storyatlas",
    entity_types=STORYATLAS_ENTITY_TYPES,
    functional_predicates=STORYATLAS_FUNCTIONAL_PREDICATES,
)
