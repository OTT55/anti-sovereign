"""Veridact Engine — proving a capture, not detecting a fake.

Veridact does not analyse pixels to guess whether media was generated. That is
an arms race detectors lose. It verifies a **capture attestation**: a device
signs the media at capture with a private key Veridact never holds, so Veridact
can check a signature and is structurally incapable of forging one.

Three verdicts, never four. There is no `FAKE` — absence of proof is not proof
of absence, and most honest media has never been attested at all.
"""

from .attestation import (
    ALTERED, CHALLENGE_TTL_SECONDS, SIGNERS, UNVERIFIED, VERIFIED_CAPTURE,
    Challenge, Device, ECDSASigner, HMACSigner, Manifest, Verdict,
    media_hash, signing_message, utc_now,
)
from .registry import AttestationError, EnrolmentError, Veridact

__all__ = [
    "Veridact", "EnrolmentError", "AttestationError",
    "media_hash", "signing_message", "utc_now",
    "Device", "Manifest", "Verdict", "Challenge",
    "VERIFIED_CAPTURE", "ALTERED", "UNVERIFIED", "CHALLENGE_TTL_SECONDS",
    "SIGNERS", "HMACSigner", "ECDSASigner",
]
