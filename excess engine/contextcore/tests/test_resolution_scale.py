"""Two regressions in entity resolution: a false-merge bug and a complexity cliff.

Both were found by measuring rather than by a failing test — the correctness one
had been silently wrong since the phase shipped, and no unit test would have
caught it because every test used a handful of hand-written names.
"""

import time

from contextcore_engine import name_similarity, resolve


def _numbered(n, template="Organisation Number {i}"):
    return [{"name": template.format(i=i), "type": "organization"} for i in range(n)]


# -- the false-merge bug ---------------------------------------------------

def test_names_differing_only_by_number_do_not_merge():
    """Regression. Bigram similarity is near-blind to digits: "Invoice 4471"
    and "Invoice 4472" share every bigram but two. Measured once as 800
    distinct organisations collapsing into a single cluster — the exact
    failure mode that silently attributes one company's records to another.
    """
    assert name_similarity("Invoice 4471", "Invoice 4472") == 0.0
    assert name_similarity("Contract 2023-001", "Contract 2023-002") == 0.0


def test_a_corpus_of_numbered_entities_stays_distinct():
    clusters = resolve(_numbered(200))
    assert len(clusters) == 200


def test_a_numbered_name_does_not_absorb_an_unnumbered_one():
    """"Acme" and "Acme 2" are a distinction worth keeping."""
    assert name_similarity("Acme", "Acme 2") == 0.0


def test_matching_numbers_still_allow_a_merge():
    """The veto is on *differing* numbers, not on numbers existing."""
    assert name_similarity("Acme 2 Corp", "Acme 2 Corporation") == 1.0


def test_the_merges_that_matter_still_happen():
    """The fix must not buy precision by destroying recall."""
    assert name_similarity("Acme Corp", "Acme Corporation") == 1.0
    assert len(resolve([{"name": "Acme Corp", "type": "organization"},
                        {"name": "Acme Corporation", "type": "organization"}])) == 1


def test_reordered_names_still_merge_through_the_blocking_index():
    """Blocking on the *set* of token initials would be faster and would break
    this — which is why any single shared initial is enough."""
    assert len(resolve([{"name": "Vane, Aldric", "type": "person"},
                        {"name": "Aldric Vane", "type": "person"}])) == 1


# -- the complexity cliff --------------------------------------------------

def test_resolution_does_not_scale_quadratically():
    """Regression: every name was compared against every cluster — 1.66s for
    800 distinct entities and roughly four times that per doubling.

    Asserts the shape of the curve, not a wall-clock number, so it means the
    same on a fast machine and a slow one.
    """
    small = _numbered(400)
    large = _numbered(800)

    start = time.perf_counter()
    resolve(small)
    small_time = time.perf_counter() - start

    start = time.perf_counter()
    resolve(large)
    large_time = time.perf_counter() - start

    # Generous: timing is noisy at these speeds. A quadratic path shows ~4x.
    assert large_time < max(small_time * 3, 0.05), \
        f"{small_time:.3f}s -> {large_time:.3f}s on 2x the data"


def test_a_large_corpus_resolves_in_reasonable_time():
    start = time.perf_counter()
    clusters = resolve(_numbered(1600))
    elapsed = time.perf_counter() - start
    assert len(clusters) == 1600
    assert elapsed < 2.0, f"took {elapsed:.2f}s"


def test_blocking_does_not_change_the_answer():
    """The optimisation must alter cost, never outcome."""
    entities = [
        {"name": "Acme Corp", "type": "organization"},
        {"name": "Acme Corporation", "type": "organization"},
        {"name": "Zenith Holdings", "type": "organization"},
        {"name": "Aldric Vane", "type": "person"},
        {"name": "Vane, Aldric", "type": "person"},
    ]
    clusters = resolve(entities)
    canonical = sorted(c.canonical for c in clusters)
    assert canonical == ["Acme Corporation", "Aldric Vane", "Zenith Holdings"]
