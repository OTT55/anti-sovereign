"""A Merkle tree that actually commits to its contents.

The two tests that matter most are the first two: they are the flaws the app's
tree has, verified against its running code before this engine was written.
"""

import pytest

from canonchain_engine import (
    LEAF_PREFIX, NODE_PREFIX, MerkleError, consistent, leaf_hash, node_hash,
    proof, root, verify,
)

A, B, C, D = ("aa" * 32, "bb" * 32, "cc" * 32, "dd" * 32)


# -- the two flaws ----------------------------------------------------------

def test_a_duplicated_last_leaf_does_not_forge_the_same_root():
    """CVE-2012-2459, and the same line of code.

    The app pairs an odd last node with itself, so `[a,b,c]` and `[a,b,c,c]`
    build the same tree and share a root. A root that two different registries
    can produce does not commit to a registry.
    """
    assert root([A, B, C]) != root([A, B, C, C])


def test_an_internal_node_cannot_pose_as_a_leaf():
    """The app hashes leaves and nodes identically, so an internal node value
    can be presented as a registered work and a proof built for it verifies —
    an inclusion proof for something nobody registered.

    Domain separation makes the two hash functions disjoint, so this fails by
    construction rather than by a check somebody has to remember.
    """
    tree = root([A, B, C, D])
    internal = node_hash(leaf_hash(A), leaf_hash(B))
    assert not verify(internal, [{"position": "right",
                                  "hash": node_hash(leaf_hash(C), leaf_hash(D))}],
                      tree)


def test_leaves_and_nodes_use_different_prefixes():
    assert LEAF_PREFIX != NODE_PREFIX
    assert leaf_hash(A) != node_hash(A, A)


# -- ordinary correctness ---------------------------------------------------

@pytest.mark.parametrize("count", [1, 2, 3, 4, 5, 7, 8, 9, 16, 17, 33])
def test_every_leaf_can_prove_itself(count):
    """Odd counts are the interesting ones — that is where promotion happens."""
    leaves = [f"{i:064x}" for i in range(count)]
    tree = root(leaves)
    for index, leaf in enumerate(leaves):
        assert verify(leaf, proof(leaves, index), tree), (count, index)


def test_a_leaf_that_is_not_in_the_tree_cannot_prove_itself():
    leaves = [A, B, C]
    assert not verify(D, proof(leaves, 0), root(leaves))


def test_a_proof_from_a_different_tree_does_not_verify():
    assert not verify(A, proof([A, B, C], 0), root([A, B, D]))


def test_order_matters():
    """Two registries holding the same works in a different order are different
    registries, and the root has to say so."""
    assert root([A, B]) != root([B, A])


def test_an_empty_registry_has_no_root():
    """Inventing one would let a registry with nothing in it prove something."""
    assert root([]) is None
    assert not verify(A, [], None)


def test_a_single_leaf_needs_no_path():
    assert proof([A], 0) == []
    assert verify(A, [], root([A]))


def test_a_proof_step_must_say_which_side():
    """Folding in the wrong order gives a different hash, so a step that does
    not say would verify against a tree it does not describe."""
    with pytest.raises(MerkleError, match="needs a side"):
        verify(A, [{"hash": B}], root([A, B]))


def test_asking_for_a_leaf_that_is_not_there_is_refused():
    with pytest.raises(MerkleError, match="No leaf at position"):
        proof([A, B], 5)
    with pytest.raises(MerkleError, match="nothing to prove"):
        proof([], 0)


def test_the_tree_is_deterministic():
    assert root([A, B, C]) == root([A, B, C])
    assert proof([A, B, C], 1) == proof([A, B, C], 1)


# -- append-only ------------------------------------------------------------

def test_growth_is_recognised_as_growth():
    assert consistent([A, B], [A, B, C, D])


def test_a_rewrite_is_not():
    """A registry that quietly rewrote history publishes a new root, and without
    this check nobody can tell that from honest growth."""
    assert not consistent([A, B], [A, D, C])
    assert not consistent([A, B, C], [A, B])


def test_a_registry_is_consistent_with_itself():
    assert consistent([A, B], [A, B])


def test_old_proofs_survive_new_registrations():
    """Leaves are only ever appended, so a proof issued today has to keep
    verifying — against the root of the day it was issued."""
    early = [A, B, C]
    early_root = root(early)
    path = proof(early, 1)

    later = early + [D, leaf_hash("e")]
    assert consistent(early, later)
    assert verify(B, path, early_root)
