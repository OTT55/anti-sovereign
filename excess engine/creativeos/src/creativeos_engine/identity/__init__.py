"""The Identity Engine — *"Identity survives applications. Everything has one identity."*

Phase 3 of `BUILD_PLAN.md`. External references let each application keep its
own key for an entity; merge aliases let two entities become one without
deleting anything or rewriting a single assertion.
"""

from .registry import ExternalRef, IdentityError, IdentityRegistry

__all__ = ["IdentityRegistry", "ExternalRef", "IdentityError"]
