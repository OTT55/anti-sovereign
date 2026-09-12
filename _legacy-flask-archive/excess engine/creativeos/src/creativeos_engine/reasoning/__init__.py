"""The Reasoning Engine — *"Never acts as simple retrieval."*

Phase 8 of `BUILD_PLAN.md`. Paths, implications from transitive and symmetric
predicates, impact analysis, and gap detection. Deterministic; every conclusion
carries the facts that produced it.
"""

from .reasoner import (
    SYMMETRIC, TRANSITIVE, Gap, Impact, Implication, Path, ReasoningEngine,
)

__all__ = [
    "ReasoningEngine", "Path", "Implication", "Impact", "Gap",
    "TRANSITIVE", "SYMMETRIC",
]
