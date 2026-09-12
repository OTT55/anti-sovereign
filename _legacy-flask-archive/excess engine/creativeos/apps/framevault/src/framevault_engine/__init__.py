"""FrameVault Engine — the domain authority for professional identity.

Two engines of its own, both built on CreativeOS's shared platform:

    Provenance   a signed claim that a creator made a specific work
    Reputation   credits earned from what other applications witnessed

The rule FrameVault owns: a credit is something another application *says
happened*, never something a creator claims about themselves.
"""

from .provenance import (
    SIGNED_FIELDS, Registration, Verdict, canonical, content_hash, sign, verify,
)
from .reputation import WEIGHTS, Credit, ReputationEngine

__all__ = [
    "content_hash", "canonical", "sign", "verify", "Registration", "Verdict",
    "SIGNED_FIELDS", "ReputationEngine", "Credit", "WEIGHTS",
]
