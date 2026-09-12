"""Phase 10 — the Storage Engine.

Content-addressed blobs with a walkable version chain.
"""

import pytest

from creativeos_engine.storage import StorageEngine, digest_of


@pytest.fixture
def storage(graph):
    return StorageEngine(graph.store.conn)


def test_a_file_is_stored_and_read_back(storage, space):
    f = storage.put(space.id, "draft.txt", "Aldric waited at the harbour.")
    assert storage.read_text(f.id) == "Aldric waited at the harbour."


def test_identity_is_the_content_not_the_name(storage, space):
    """The same bytes are the same blob whatever they are called."""
    a = storage.put(space.id, "draft.txt", "same bytes")
    b = storage.put(space.id, "copy.txt", "same bytes")
    assert a.digest == b.digest
    assert a.id != b.id


def test_changing_the_content_changes_the_identity(storage, space):
    """Provenance depends on this: "the fact came from this draft" is
    meaningless if the draft can change underneath the claim."""
    a = storage.put(space.id, "draft.txt", "version one")
    b = storage.put(space.id, "draft.txt", "version two", replaces=a.id)
    assert a.digest != b.digest
    assert storage.read_text(a.id) == "version one"   # the original is intact


def test_versions_form_a_walkable_chain(storage, space):
    v1 = storage.put(space.id, "draft.txt", "one")
    v2 = storage.put(space.id, "draft.txt", "two", replaces=v1.id)
    v3 = storage.put(space.id, "draft.txt", "three", replaces=v2.id)

    history = storage.history(v3.id)
    assert [f.version for f in history] == [1, 2, 3]
    assert [storage.read_text(f.id) for f in history] == ["one", "two", "three"]


def test_latest_returns_the_newest_version(storage, space):
    v1 = storage.put(space.id, "draft.txt", "one")
    storage.put(space.id, "draft.txt", "two", replaces=v1.id)
    assert storage.read_text(storage.latest(space.id, "draft.txt").id) == "two"


def test_replacing_an_unknown_file_is_rejected(storage, space):
    with pytest.raises(ValueError):
        storage.put(space.id, "draft.txt", "x", replaces="FIL-NOPE")


def test_a_file_can_be_attached_to_an_entity(graph, storage, space):
    entity = graph.create_entity(space.id, "character", "Aldric Vane")
    storage.put(space.id, "portrait.png", b"\x89PNG", entity_id=entity.id)
    assert [f.name for f in storage.for_entity(entity.id)] == ["portrait.png"]


def test_duplicate_content_is_reported(storage, space):
    storage.put(space.id, "a.txt", "identical")
    storage.put(space.id, "b.txt", "identical")
    duplicates = storage.duplicates(space.id)
    assert len(duplicates) == 1
    assert len(next(iter(duplicates.values()))) == 2


def test_identical_bytes_are_stored_once(storage, space):
    storage.put(space.id, "a.txt", "identical")
    storage.put(space.id, "b.txt", "identical")
    stats = storage.stats(space.id)
    assert stats["files"] == 2
    assert stats["blobs"] == 1


def test_binary_content_round_trips(storage, space):
    raw = bytes(range(256))
    f = storage.put(space.id, "blob.bin", raw)
    assert storage.read(f.id) == raw


def test_digest_is_sha256_of_the_bytes(storage, space):
    f = storage.put(space.id, "draft.txt", "hello")
    assert f.digest == digest_of(b"hello")
