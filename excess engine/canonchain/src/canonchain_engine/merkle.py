"""A Merkle tree that actually commits to its contents.

Canonchain's whole claim is that one 64-hex root fingerprints the entire
registry, so anyone can check an entry is genuinely in it and the server cannot
silently drop or fake one. That claim rests entirely on the tree, and the
app's tree does not support it. Two flaws, both verified against the running
code before this was written.

## 1. Odd nodes are duplicated (CVE-2012-2459)

    level = [_pair(level[i], level[i+1] if i+1 < len(level) else level[i]), ...]

An odd last node is paired **with itself**. So `[a, b, c]` and `[a, b, c, c]`
build the same tree and produce the same root:

    >>> merkle_root([a, b, c]) == merkle_root([a, b, c, c])
    True

A root that two different registries can share does not commit to a registry.
This is the flaw that hit Bitcoin in 2012, and it is the same line of code.

## 2. An internal node is accepted as a leaf

Leaves and internal nodes are hashed identically, so a node value can be
presented as a registered work and a proof built for it verifies:

    >>> verify_proof(_pair(a, b), [{"position": "right", "hash": _pair(c, c)}], root)
    True

That is an inclusion proof for something nobody ever registered. For a rights
registry it is the worst possible failure: the proof is the product.

## The fix, and why it is this one

**Domain separation**, as RFC 6962 (Certificate Transparency) specifies:

    leaf hash      = SHA256(0x00 ‖ value)
    internal node  = SHA256(0x01 ‖ left ‖ right)

The prefixes make the two hash functions disjoint, so no internal node can ever
equal a leaf hash and flaw 2 disappears by construction rather than by a check
somebody has to remember.

**Odd nodes are promoted, not duplicated.** A node with no sibling is carried up
to the next level unchanged. The tree then depends on the exact leaf count, so
`[a, b, c]` and `[a, b, c, c]` build different trees and flaw 1 disappears too.

Both are standard. Neither is clever. They are simply what a Merkle tree has to
do to mean what everyone assumes it means.
"""

import hashlib

#: Domain-separation prefixes. Their entire job is to make the leaf and node
#: hash functions disjoint, so a value from one can never be mistaken for the
#: other. One byte, and it is what makes an inclusion proof a proof.
LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"


class MerkleError(Exception):
    """Raised when a tree cannot be built or a proof cannot be made."""


def _as_bytes(value):
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        try:
            return bytes.fromhex(value)
        except ValueError:
            return value.encode("utf-8")
    raise MerkleError(f"Cannot hash {type(value).__name__}.")


def leaf_hash(value):
    """`SHA256(0x00 ‖ value)` — the hash of a registered work."""
    return hashlib.sha256(LEAF_PREFIX + _as_bytes(value)).hexdigest()


def node_hash(left, right):
    """`SHA256(0x01 ‖ left ‖ right)` — the hash of an internal node."""
    return hashlib.sha256(
        NODE_PREFIX + _as_bytes(left) + _as_bytes(right)).hexdigest()


def _level_up(level):
    """One level of the tree.

    A node with no sibling is **promoted** unchanged rather than paired with
    itself. Duplicating it is what lets two different leaf sets share a root.
    """
    out = []
    for i in range(0, len(level), 2):
        if i + 1 < len(level):
            out.append(node_hash(level[i], level[i + 1]))
        else:
            out.append(level[i])
    return out


def root(leaves):
    """The root committing to exactly these leaves, in this order.

    `None` for an empty registry — an empty tree has no root, and inventing one
    would let a registry with nothing in it produce a proof of something.
    """
    if not leaves:
        return None
    level = [leaf_hash(leaf) for leaf in leaves]
    while len(level) > 1:
        level = _level_up(level)
    return level[0]


def proof(leaves, index):
    """The sibling path needed to recompute the root from one leaf.

    Each step says which side the sibling is on, because folding in the wrong
    order gives a different hash — and a proof that does not say would verify
    against a tree it does not describe.
    """
    if not leaves:
        raise MerkleError("An empty registry has nothing to prove.")
    if not 0 <= index < len(leaves):
        raise MerkleError(
            f"No leaf at position {index}; the registry holds {len(leaves)}.")

    path = []
    level = [leaf_hash(leaf) for leaf in leaves]
    position = index

    while len(level) > 1:
        if position % 2 == 0:
            if position + 1 < len(level):
                path.append({"position": "right", "hash": level[position + 1]})
            # No sibling: this node is promoted, so nothing is folded in and
            # the path records no step. Appending a duplicate here is exactly
            # the bug the promotion rule exists to avoid.
        else:
            path.append({"position": "left", "hash": level[position - 1]})
        position //= 2
        level = _level_up(level)

    return path


def verify(value, path, expected_root):
    """Recompute the root from one value and its path.

    The value is hashed **as a leaf**, which is the whole defence: an internal
    node presented here hashes to something no tree contains, so a forged proof
    for an unregistered work cannot verify.
    """
    if expected_root is None:
        return False
    computed = leaf_hash(value)
    for step in path:
        sibling = step.get("hash")
        side = step.get("position")
        if side == "right":
            computed = node_hash(computed, sibling)
        elif side == "left":
            computed = node_hash(sibling, computed)
        else:
            raise MerkleError(f"A proof step needs a side, not '{side}'.")
    return computed == expected_root


def consistent(old_leaves, new_leaves):
    """Is `new_leaves` an append-only extension of `old_leaves`?

    The question a published checkpoint invites and the app never answers: a
    registry that quietly rewrote history would publish a new root, and without
    this nobody could tell that from honest growth. Append-only is the promise;
    this is how it is checked.
    """
    if len(new_leaves) < len(old_leaves):
        return False
    return list(new_leaves[:len(old_leaves)]) == list(old_leaves)


__all__ = ["root", "proof", "verify", "consistent", "leaf_hash", "node_hash",
           "MerkleError", "LEAF_PREFIX", "NODE_PREFIX"]
