"""Writing a reading into the CreativeOS graph.

This is the layering made concrete. StoryAtlas decided that this name is a
character and that this verb is a death; CreativeOS stores it as an entity and a
sourced assertion over a valid-time window, and then applies its own
verification without knowing what a character *is*.

Note the division of labour:

* StoryAtlas computes a **lifespan** — born 1102, died 1147 — because knowing
  that a death bounds a life is narrative knowledge.
* CreativeOS turns that into `ValidWindow(1102, 1147)` on an `alive` assertion,
  and from then on any fact placed outside that window contradicts it
  *automatically*. That check is universal, so it lives there.

Neither layer could do the other's half, which is the point of the boundary.
"""

STORYATLAS_TYPES = (
    "character", "location", "organization", "event",
    "story", "scene", "artifact", "other",
)

STORYATLAS_FUNCTIONAL = ("status", "alive", "born_in", "died_in", "title", "rank")


def storyatlas_pack():
    """StoryAtlas's vocabulary, declared to CreativeOS.

    Built here rather than imported from CreativeOS so the dependency points the
    right way: StoryAtlas knows about CreativeOS, never the reverse.
    """
    from creativeos_engine.graph import DomainPack
    return DomainPack(
        name="storyatlas",
        entity_types=STORYATLAS_TYPES,
        functional_predicates=STORYATLAS_FUNCTIONAL,
    )


def commit(reading, graph, space_id, source_ref_prefix="draft"):
    """Write everything the reading understood into the graph.

    Only what the engine is confident about. Anything it raised a question over
    stays out until a human answers — a draft is not evidence until someone
    confirms the engine read it correctly.

    Returns a summary of what was written.
    """
    entity_ids = {}

    def entity_for(name, kind="character"):
        if name not in entity_ids:
            entity_ids[name] = graph.create_entity(space_id, kind, name).id
        return entity_ids[name]

    # Characters first, so events can point at them.
    for name in reading.names:
        entity_for(name)

    spans = reading.lifespans()
    written_facts = 0

    # A lifespan becomes a bounded `alive` assertion. From here CreativeOS can
    # catch a character acting outside their own life without knowing what a
    # character is.
    from creativeos_engine.graph import ValidWindow
    for name, (born, died) in spans.items():
        if born is None and died is None:
            continue
        graph.assert_attribute(
            entity_for(name), "alive", "true",
            valid=ValidWindow(born, died),
            source_kind="manuscript", source_ref=f"{source_ref_prefix}:lifespan",
            confidence=1.0,
        )
        written_facts += 1

    # Events become relationships or attributes, each citing its sentence.
    questioned = {id(q.evidence) for q in reading.questions}
    written_events = 0
    for placement in reading.timeline.placements:
        event = placement.event
        subject = event.subject
        if not subject or event.confidence < 0.7:
            continue  # unconfirmed — belongs in questions, not in the graph

        window = ValidWindow(placement.year, None) if placement.is_dated else ValidWindow()
        ref = f"{source_ref_prefix}:s{event.sentence_index}"

        if event.agent and event.patient and event.agent != event.patient:
            graph.assert_relationship(
                entity_for(event.agent), event.kind, entity_for(event.patient),
                valid=window, source_kind="manuscript", source_ref=ref,
                confidence=event.confidence,
            )
        else:
            graph.assert_attribute(
                entity_for(subject), event.kind, str(placement.year or "unknown"),
                valid=window, source_kind="manuscript", source_ref=ref,
                confidence=event.confidence,
            )

        if event.place:
            graph.assert_relationship(
                entity_for(subject), "located_at", entity_for(event.place, "location"),
                valid=window, source_kind="manuscript", source_ref=ref,
                confidence=event.confidence,
            )
        written_events += 1

    return {
        "entities": len(entity_ids),
        "lifespans": written_facts,
        "events": written_events,
        "held_for_confirmation": len(reading.questions),
    }
