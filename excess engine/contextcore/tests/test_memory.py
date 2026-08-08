"""Phase 4 — the Memory Engine: version chains and knowledge history."""

import sqlite3

import pytest

from contextcore_engine.memory import MemoryEngine


@pytest.fixture
def memory():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return MemoryEngine(conn)


def _facts(*labels):
    return [{"kind": "entity", "signature": label.lower(), "label": label}
            for label in labels]


# -- version chains ---------------------------------------------------------

def test_a_first_document_is_version_one(memory):
    assert memory.record_version("CX-1", "hash1") == 1


def test_a_successor_increments(memory):
    memory.record_version("CX-1", "hash1")
    assert memory.record_version("CX-2", "hash2", previous_doc_id="CX-1") == 2
    assert memory.record_version("CX-3", "hash3", previous_doc_id="CX-2") == 3


def test_the_chain_reads_oldest_first(memory):
    memory.record_version("CX-1", "h1")
    memory.record_version("CX-2", "h2", previous_doc_id="CX-1")
    memory.record_version("CX-3", "h3", previous_doc_id="CX-2")
    assert [v["doc_id"] for v in memory.chain("CX-3")] == ["CX-1", "CX-2", "CX-3"]


def test_any_member_can_see_the_whole_chain(memory):
    """A caller rarely holds the newest id."""
    memory.record_version("CX-1", "h1")
    memory.record_version("CX-2", "h2", previous_doc_id="CX-1")
    assert len(memory.chain("CX-1")) == 1     # nothing before it
    assert len(memory.chain("CX-2")) == 2


def test_an_old_id_resolves_forward_to_the_current_one(memory):
    memory.record_version("CX-1", "h1")
    memory.record_version("CX-2", "h2", previous_doc_id="CX-1")
    memory.record_version("CX-3", "h3", previous_doc_id="CX-2")
    assert memory.latest("CX-1") == "CX-3"


def test_an_unknown_document_has_no_version(memory):
    assert memory.version_of("CX-NOPE") is None


# -- knowledge history ------------------------------------------------------

def test_facts_in_a_first_version_are_all_new(memory):
    memory.record_version("CX-1", "h1")
    result = memory.observe("CX-1", _facts("Acme Corporation", "Aldric Vane"))
    assert sorted(result["added"]) == ["Acme Corporation", "Aldric Vane"]
    assert result["closed"] == []


def test_a_fact_that_persists_is_retained_not_re_added(memory):
    memory.record_version("CX-1", "h1")
    memory.observe("CX-1", _facts("Acme Corporation"))
    memory.record_version("CX-2", "h2", previous_doc_id="CX-1")
    result = memory.observe("CX-2", _facts("Acme Corporation"))
    assert result["retained"] == ["Acme Corporation"]
    assert result["added"] == []


def test_a_fact_that_disappears_is_closed(memory):
    """The question a document store normally cannot answer: what did we stop
    believing? A fact being removed is a decision somebody made."""
    memory.record_version("CX-1", "h1")
    memory.observe("CX-1", _facts("Acme Corporation", "Zenith Holdings"))
    memory.record_version("CX-2", "h2", previous_doc_id="CX-1")
    result = memory.observe("CX-2", _facts("Acme Corporation"))

    assert result["closed"] == ["Zenith Holdings"]
    assert [f["label"] for f in memory.closed_facts("CX-2")] == ["Zenith Holdings"]


def test_a_closed_fact_that_returns_is_reopened(memory):
    memory.record_version("CX-1", "h1")
    memory.observe("CX-1", _facts("Zenith Holdings"))
    memory.record_version("CX-2", "h2", previous_doc_id="CX-1")
    memory.observe("CX-2", _facts())
    assert memory.closed_facts("CX-2")

    memory.record_version("CX-3", "h3", previous_doc_id="CX-2")
    memory.observe("CX-3", _facts("Zenith Holdings"))
    assert memory.closed_facts("CX-3") == []


def test_live_facts_exclude_the_closed_ones(memory):
    memory.record_version("CX-1", "h1")
    memory.observe("CX-1", _facts("Acme Corporation", "Zenith Holdings"))
    memory.record_version("CX-2", "h2", previous_doc_id="CX-1")
    memory.observe("CX-2", _facts("Acme Corporation"))

    assert [f["label"] for f in memory.live_facts("CX-2")] == ["Acme Corporation"]


def test_nothing_is_deleted_when_a_fact_closes(memory):
    """Append-only: the record of what was believed is itself the product."""
    memory.record_version("CX-1", "h1")
    memory.observe("CX-1", _facts("Zenith Holdings"))
    memory.record_version("CX-2", "h2", previous_doc_id="CX-1")
    memory.observe("CX-2", _facts())

    closed = memory.closed_facts("CX-2")
    assert closed[0]["label"] == "Zenith Holdings"
    assert closed[0]["first_seen"]     # still knows when it appeared


def test_an_unrelated_document_does_not_close_anything(memory):
    """Only the document's own lineage counts — another document omitting a
    fact says nothing about this one."""
    memory.record_version("CX-1", "h1")
    memory.observe("CX-1", _facts("Acme Corporation"))
    memory.record_version("CX-9", "h9")          # separate lineage
    memory.observe("CX-9", _facts("Something Else"))

    assert [f["label"] for f in memory.live_facts("CX-1")] == ["Acme Corporation"]


# -- timeline and summary ---------------------------------------------------

def test_the_timeline_walks_every_version(memory):
    memory.record_version("CX-1", "h1")
    memory.observe("CX-1", _facts("Acme Corporation"))
    memory.record_version("CX-2", "h2", previous_doc_id="CX-1", similarity=0.82)
    memory.observe("CX-2", _facts("Acme Corporation", "New Fact"))

    timeline = memory.timeline("CX-2")
    assert [e["version"] for e in timeline] == [1, 2]
    assert timeline[1]["similarity_to_previous"] == 0.82


def test_the_summary_counts_both_histories(memory):
    memory.record_version("CX-1", "h1")
    memory.observe("CX-1", _facts("A", "B"))
    memory.record_version("CX-2", "h2", previous_doc_id="CX-1")
    memory.observe("CX-2", _facts("A"))

    summary = memory.summary("CX-2")
    assert summary["versions"] == 2
    assert summary["current_version"] == 2
    assert summary["live_facts"] == 1
    assert summary["closed_facts"] == 1


def test_observation_is_deterministic(memory):
    memory.record_version("CX-1", "h1")
    first = memory.observe("CX-1", _facts("A", "B"))
    assert sorted(first["added"]) == ["A", "B"]
    again = memory.observe("CX-1", _facts("A", "B"))
    assert again["added"] == []          # nothing new the second time
