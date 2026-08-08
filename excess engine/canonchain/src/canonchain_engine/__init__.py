"""Canonchain Engine — proving who held these exact bytes first.

A cryptographic rights registry. It answers one narrow question and refuses the
broader one: registering a hash proves you *held* those bytes at that time, not
that you made them.

Two modules:

* `merkle`   — a tree that actually commits to its contents
* `registry` — registrations, first-claim ordering, proofs and checkpoints

The tree is the point. The app's version has two flaws, both verified against
the running code: odd nodes are duplicated, so `[a,b,c]` and `[a,b,c,c]` share a
root; and leaves and internal nodes are hashed identically, so an internal node
can be passed off as a registered work and its forged proof verifies. RFC 6962
domain separation fixes both by construction.

Deterministic, no network, no model.

    from canonchain_engine import Canonchain, file_hash

    chain = Canonchain()
    entry = chain.register("ott", file_hash(b"my film"), filename="cut.mov")

    proof = chain.proof_for(entry.file_hash)
    chain.verify(entry.file_hash, proof["path"], proof["root"])   # True
"""

from .merkle import (
    LEAF_PREFIX, NODE_PREFIX, MerkleError, consistent, leaf_hash, node_hash,
    proof, root, verify,
)
from .registry import (
    Canonchain, Checkpoint, DuplicateRegistration, HMACSigner, Registration,
    RegistryError, file_hash,
)

__all__ = [
    # the registry
    "Canonchain", "Registration", "Checkpoint", "HMACSigner",
    "RegistryError", "DuplicateRegistration", "file_hash",
    # the tree
    "root", "proof", "verify", "consistent", "leaf_hash", "node_hash",
    "MerkleError", "LEAF_PREFIX", "NODE_PREFIX",
]
