"""The Verification Engine — *"Truth should never be assumed."*

Phase 7 of `BUILD_PLAN.md`. Evidence tracking with independent-source
weighting, ambiguity detection, relationship validation against lifespans, and
a single certainty number with its reasoning attached.
"""

from .verifier import (
    Ambiguity, Evidence, InvalidRelationship, VerificationEngine, Verdict,
)

__all__ = [
    "VerificationEngine", "Verdict", "Evidence", "Ambiguity", "InvalidRelationship",
]
