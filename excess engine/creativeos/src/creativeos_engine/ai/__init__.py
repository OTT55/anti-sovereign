"""The AI Orchestrator — *"AI is infrastructure. Not product."*

Phase 6 of `BUILD_PLAN.md`, built last on purpose. Provider routing by
capability, prompts built from the Context Engine, and an honest extractive
fallback that makes this fully functional with no model configured at all.
"""

from .orchestrator import AIOrchestrator, Answer, Provider

__all__ = ["AIOrchestrator", "Answer", "Provider"]
