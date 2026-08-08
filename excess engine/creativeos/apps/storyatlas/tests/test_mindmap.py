"""Phase 11 — the draft as a graph, and as an Obsidian vault.

*"How does something like this work with a mind map?"* — by being a set of notes
you can open, not a picture of circles and lines.
"""

import pytest

from storyatlas_engine import analyse, mindmap, read

DRAFT = """CHAPTER ONE

Aldric Vane was born in the year 1100. Mara Sadel was the sister of Aldric Vane.

***

In the year 1140, Aldric Vane was crowned at Dawnhold. Mara Sadel watched.

***

Mara Sadel died in the year 1150.

***

In the year 1180, Mara Sadel spoke at Dawnhold.
"""


@pytest.fixture
def reading():
    return read(DRAFT)


@pytest.fixture
def report():
    return analyse(DRAFT)


def test_a_map_has_nodes_for_the_things_that_exist(reading):
    graph = mindmap.build(reading)
    labels = {n.label for n in graph.nodes}
    assert "Aldric Vane" in labels
    assert "Dawnhold" in labels


def test_shared_scenes_become_a_weighted_edge(reading):
    graph = mindmap.build(reading)
    edges = [e for e in graph.edges if e.kind == "appears-with"]
    assert edges
    assert all(e.weight >= 1 for e in edges)


def test_duplicate_edges_are_merged_not_repeated(reading):
    """A pair linked five times by five scenes is one relationship of strength
    five, not five relationships."""
    graph = mindmap.build(reading)
    keys = [(e.source, e.target, e.kind) for e in graph.edges]
    assert len(keys) == len(set(keys))


def test_centrality_is_degree_a_writer_can_verify(reading):
    graph = mindmap.build(reading)
    ranked = graph.central(2)
    assert ranked
    assert ranked[0][1] >= ranked[-1][1]


def test_mermaid_renders_only_connected_nodes(reading):
    text = mindmap.build(reading).to_mermaid()
    assert text.startswith("graph TD")
    assert "Aldric_Vane" in text


def test_an_outline_is_text_not_a_picture(reading):
    outline = mindmap.build(reading).to_outline()
    assert "Characters" in outline
    assert "Aldric Vane" in outline


def test_the_map_serialises(reading):
    payload = mindmap.build(reading).to_dict()
    assert payload["nodes"] and payload["edges"]
    assert all("kind" in n for n in payload["nodes"])


# -- the vault --------------------------------------------------------------

def test_a_vault_has_one_note_per_entity(reading):
    files = mindmap.vault(reading)
    assert "Aldric Vane.md" in files
    assert "Index.md" in files


def test_notes_link_to_each_other(reading):
    note = mindmap.vault(reading)["Aldric Vane.md"]
    assert "[[" in note


def test_a_finding_lives_on_the_page_of_the_thing_it_is_about(reading, report):
    """The contradiction about Mara is on Mara's page, where the writer will be
    when it matters — not only in a report they have to remember to open."""
    note = mindmap.vault(reading, report)["Mara Sadel.md"]
    assert "Needs attention" in note
    assert "1180" in note


def test_a_character_note_records_where_and_when(reading):
    note = mindmap.vault(reading)["Aldric Vane.md"]
    assert "Where and when" in note
    assert "Dawnhold" in note


def test_an_era_note_names_who_was_offstage(reading):
    files = mindmap.vault(reading)
    era_notes = [c for n, c in files.items() if n.startswith("Year ")]
    assert era_notes
    assert any("offstage" in note.lower() for note in era_notes)


def test_a_filename_is_always_usable():
    reading = read('In the year 1100, Aldric Vane was crowned at Dawn/Hold.')
    for name in mindmap.vault(reading):
        assert not set(name) & set('\\/:*?"<>|')


def test_the_vault_writes_to_disk(reading, tmp_path):
    written = mindmap.write_vault(reading, str(tmp_path))
    assert written
    assert (tmp_path / "Index.md").read_text(encoding="utf-8")


def test_an_empty_draft_produces_a_vault_that_does_not_crash():
    files = mindmap.vault(read(""))
    assert "Index.md" in files


def test_the_map_is_deterministic(reading):
    assert mindmap.build(reading).to_mermaid() == \
           mindmap.build(read(DRAFT)).to_mermaid()
