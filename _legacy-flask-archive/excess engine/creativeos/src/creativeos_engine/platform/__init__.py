"""The Platform Engine — *"Everything shared."*

Part of Phase 10. Accounts, organizations, membership, roles and permissions,
plus notifications over the Event Engine.

Password hashing, sessions and billing are deliberately absent: they are a
library call and a payment provider, not architecture. `authenticate()` takes a
verifier callback so credentials never pass through this module.
"""

from .engine import (
    ROLE_PERMISSIONS, ROLES, Account, Organization, PlatformEngine, PlatformError,
)
from .money import (
    TOTAL_PERCENT, Share, SplitError, from_pounds, split_pence, to_pounds,
    total_of, validate_split,
)

__all__ = [
    "PlatformEngine", "PlatformError", "Account", "Organization",
    "ROLES", "ROLE_PERMISSIONS",
    # money — shared, because more than one application splits a payment
    "Share", "SplitError", "validate_split", "split_pence", "total_of",
    "to_pounds", "from_pounds", "TOTAL_PERCENT",
]
