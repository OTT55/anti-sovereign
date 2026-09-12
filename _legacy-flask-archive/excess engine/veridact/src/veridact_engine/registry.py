"""The Veridact registry — enrolment, attestation, and the verdict.

Holds the state the attestation logic operates over: which devices are enrolled,
which challenges are outstanding, and which manifests exist.

The ordering inside `verify()` is the design. Checks run cheapest-first and each
one can only *lower* the verdict, never raise it — so a later check cannot
rescue something an earlier one already disproved. That ordering is what makes
"ALTERED" and "UNVERIFIED" reliably different answers rather than two names for
the same uncertainty.
"""

import secrets
from datetime import datetime, timezone

from .attestation import (
    ALTERED, CHALLENGE_TTL_SECONDS, SIGNERS, UNVERIFIED, VERIFIED_CAPTURE,
    Challenge, Device, Manifest, Verdict, new_challenge, signing_message, utc_now,
)


class EnrolmentError(Exception):
    """Raised when a device cannot be enrolled or is not who it claims."""


class AttestationError(Exception):
    """Raised when a capture cannot be attested."""


class Veridact:
    """The registry. In-memory by design — persistence is the app's job."""

    def __init__(self, clock=None):
        self.devices = {}
        self.challenges = {}
        self.manifests = {}
        self._by_hash = {}
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    # -- enrolment ---------------------------------------------------------

    def enrol(self, handle, public_key, algorithm="ecdsa-p256"):
        """Register a device by its **public** key.

        Rejects an unknown algorithm rather than storing it and failing later:
        a device enrolled under a scheme nothing can verify is a device whose
        every future capture silently returns UNVERIFIED.
        """
        handle = (handle or "").strip()
        if not handle:
            raise EnrolmentError("A device handle is required.")
        if algorithm not in SIGNERS:
            raise EnrolmentError(
                f"Unknown algorithm '{algorithm}'. Known: {', '.join(sorted(SIGNERS))}.")
        if handle in self.devices:
            raise EnrolmentError(f"'{handle}' is already enrolled.")
        if not (public_key or "").strip():
            raise EnrolmentError("A public key is required.")

        device = Device(handle, public_key, algorithm, utc_now())
        self.devices[handle] = device
        return device

    def device(self, handle):
        return self.devices.get(handle)

    # -- freshness ---------------------------------------------------------

    def issue_challenge(self):
        """A one-time nonce that makes a signature provably *live*.

        Without this a signature could be computed once and replayed onto any
        file forever. The device must fold it into what it signs.

        Stamped from **this registry's clock**, not the wall clock. Issuing
        against one time source and expiring against another makes the TTL
        meaningless — the window can come out negative, enormous, or correct
        by luck, and the freshness guarantee is only as good as the two
        readings agreeing.
        """
        challenge = Challenge(secrets.token_hex(16), self._clock().isoformat())
        self.challenges[challenge.nonce] = challenge
        return challenge

    def _consume(self, nonce):
        challenge = self.challenges.get(nonce)
        if challenge is None:
            raise AttestationError("Unknown challenge — a capture must request one first.")
        if challenge.is_used:
            raise AttestationError(
                "That challenge has already been used. Each one signs exactly one "
                "capture, so a replayed signature cannot pass as a new one.")
        if challenge.is_expired(self._clock()):
            raise AttestationError(
                f"That challenge expired (they last {CHALLENGE_TTL_SECONDS}s). "
                "Request a new one and capture again.")
        challenge.used_at = self._clock().isoformat()
        return challenge

    # -- attestation -------------------------------------------------------

    def attest(self, handle, media_hash, label, challenge, captured_at, signature):
        """Record a device's signed statement about a capture.

        The signature is checked **before** anything is stored. A manifest that
        does not verify is not a weak manifest, it is not a manifest — storing
        it would put an unverifiable record in the registry that later reads as
        ALTERED and blames the file rather than the submission.
        """
        device = self.devices.get(handle)
        if device is None:
            raise AttestationError(f"'{handle}' is not enrolled.")

        self._consume(challenge)

        message = signing_message(media_hash, challenge, captured_at)
        signer = SIGNERS[device.algorithm]
        if not signer.verify(device.public_key, message, signature):
            raise AttestationError(
                "The signature does not match this device's public key. The "
                "capture was not accepted.")

        manifest = Manifest(
            manifest_id="VD-" + secrets.token_hex(6).upper(),
            device_handle=handle, media_hash=media_hash, label=label,
            challenge=challenge, captured_at=captured_at,
            received_at=self._clock().isoformat(),
            algorithm=device.algorithm, signature=signature,
        )
        self.manifests[manifest.manifest_id] = manifest
        self._by_hash.setdefault(media_hash, []).append(manifest)
        return manifest

    # -- verification ------------------------------------------------------

    def verify(self, media_hash):
        """What can be proved about this file.

        Checks run cheapest-first and each can only lower the verdict:

          1. Is there a manifest for these exact bytes?   no  -> UNVERIFIED
          2. Is the signing device still enrolled?        no  -> UNVERIFIED
          3. Does the signature still verify?             no  -> ALTERED
                                                          yes -> VERIFIED_CAPTURE

        Step 1 failing means *we have never seen this*, which is not an
        accusation. Step 3 failing means *we have seen this and it does not
        match what was signed* — a genuinely different statement, and the only
        one that points at the file.
        """
        checks = {"manifest_found": False, "device_enrolled": False,
                  "signature_valid": False}

        manifests = self._by_hash.get(media_hash, [])
        if not manifests:
            return Verdict(
                UNVERIFIED,
                "No capture attestation exists for this file. That is not a "
                "claim it is fake — most media has never been attested at all.",
                checks=checks)
        checks["manifest_found"] = True

        manifest = manifests[-1]
        device = self.devices.get(manifest.device_handle)
        if device is None:
            return Verdict(
                UNVERIFIED,
                f"The signing device '{manifest.device_handle}' is no longer "
                "enrolled, so its signature cannot be checked.",
                manifest=manifest, checks=checks)
        checks["device_enrolled"] = True

        signer = SIGNERS.get(device.algorithm)
        if signer is None:
            return Verdict(
                UNVERIFIED,
                f"No verifier for '{device.algorithm}' is available here.",
                manifest=manifest, device=device, checks=checks)

        if not signer.verify(device.public_key, manifest.message(), manifest.signature):
            return Verdict(
                ALTERED,
                "A capture was attested for this file, but the signature no "
                "longer matches — the record or the media has changed since.",
                manifest=manifest, device=device, checks=checks)

        checks["signature_valid"] = True
        return Verdict(
            VERIFIED_CAPTURE,
            f"Captured by {device.handle} at {manifest.captured_at} and "
            "unchanged since.",
            manifest=manifest, device=device, checks=checks)

    # -- reading -----------------------------------------------------------

    def manifests_for(self, handle):
        return [m for m in self.manifests.values() if m.device_handle == handle]

    def revoke(self, handle):
        """Remove a device.

        Its manifests are deliberately **kept**. Deleting them would erase the
        record that a capture was ever attested; keeping them means verification
        degrades honestly to UNVERIFIED, which is the truth — the claim exists,
        it just can no longer be checked.
        """
        return self.devices.pop(handle, None)

    def summary(self):
        return {
            "devices": len(self.devices),
            "manifests": len(self.manifests),
            "challenges_outstanding": sum(
                1 for c in self.challenges.values() if not c.is_used),
        }
