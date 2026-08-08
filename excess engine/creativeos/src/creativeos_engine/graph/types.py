"""The Knowledge Engine's type system — deliberately empty of meaning.

Constitution v2.0: *"CreativeOS understands entities. StoryAtlas understands
kingdoms."* and *"CreativeOS owns universal intelligence. Applications own
domain intelligence. **Never mix them.**"*

So the core ships **no vocabulary at all**. There is no `CHARACTER`, no `SCENE`,
no `MAGIC_SYSTEM` in here, and there never should be — the moment the core knows
what a scene is, CreativeOS has become a storytelling application instead of the
platform beneath one.

Instead an application declares the types it needs as a `DomainPack`, and the
graph enforces that every entity's `kind` was actually declared. That inverts the
dependency the right way round: StoryAtlas depends on CreativeOS, CreativeOS
knows nothing about StoryAtlas.

The predecessor of this module was a fixed `EntityKind` enum listing creative
concepts directly in the core. That was correct under Constitution v1.0, where
CreativeOS *was* the creative-intelligence engine. Under v2.0 it is a boundary
violation, and this registry is its replacement.
"""

import re
from dataclasses import dataclass, field

#: A type name is a lowercase slug: letters, digits, underscores. Normalizing
#: here means "Character", "character" and " CHARACTER " are one type, so two
#: applications spelling it differently cannot silently fork the vocabulary.
_TYPE_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


class TypeError_(Exception):
    """Raised when a type name is malformed or was never declared."""


def normalize_type(name):
    """Return the canonical form of a type name, or raise."""
    if not isinstance(name, str):
        raise TypeError_(f"Type name must be a string, got {type(name).__name__}.")
    slug = name.strip().lower().replace("-", "_").replace(" ", "_")
    if not _TYPE_NAME.match(slug):
        raise TypeError_(
            f"'{name}' is not a valid type name. Use a lowercase slug starting "
            "with a letter, e.g. 'character' or 'magic_system'."
        )
    return slug


@dataclass(frozen=True)
class DomainPack:
    """One application's vocabulary, handed to CreativeOS at space creation.

    `entity_types` are the node kinds the application will create.

    `functional_predicates` are the predicates that may hold **at most one value
    at any one moment** — the only ones eligible to contradict each other. A
    character has one `status` at a time but may have many `trait`s. This is
    domain knowledge, not universal knowledge: only the application knows that
    `power_tier` is single-valued and `affinity` is not, which is exactly why
    the core cannot guess it.
    """

    name: str
    entity_types: tuple = ()
    functional_predicates: tuple = ()

    def __post_init__(self):
        object.__setattr__(self, "entity_types",
                           tuple(normalize_type(t) for t in self.entity_types))
        object.__setattr__(self, "functional_predicates",
                           tuple(sorted(set(self.functional_predicates))))
