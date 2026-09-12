"""The Intelligence Engine — *"The brain of CreativeOS."*

Phase 9 of `BUILD_PLAN.md`. Coordinates Search, Context, Reasoning and
Verification to answer the constitution's six questions. Contains almost no
logic of its own, deliberately.
"""

from .assistant import Answer, Assistant
from .engine import Briefing, IntelligenceEngine

__all__ = ["IntelligenceEngine", "Briefing", "Assistant", "Answer"]
