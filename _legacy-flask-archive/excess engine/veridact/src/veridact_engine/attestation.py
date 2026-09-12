"""Veridact's Attestation Engine — proving a capture, not detecting a fake.

The decision the whole product rests on, taken in the app's ADR 0001: Veridact
does **not** analyse pixels to guess whether something was generated. That is an
arms race between detectors and generators which detectors lose, and it gets
harder every year.

Instead it verifies a **capture attestation**. A device signs the media at the
moment of capture with a private key Veridact never sees. Veridact holds only
the public key, so it can check a signature and is *structurally incapable* of
forging one — which is what makes its answer worth anything.

Three properties have to hold together, and each defeats a specific attack:

* **The signature covers the media hash.** Edit one frame and the hash changes
  and the signature no longer verifies. Defeats tampering.
* **The signature covers a server-issued nonce.** Without it, a signature could
  be computed once and replayed onto any file forever. Defeats replay.
* **The nonce expires and is single-use.** Defeats a captured nonce being
  hoarded and used later.

And the rule that governs every answer: **Veridact never says "fake."** It says
what it can prove — this is a verified capture, this has been altered, or it
has no attestation at all. Absence of proof is not proof of absence, and a
product that blurs those two is lying about what it knows.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

#: How long a freshness challenge stays valid. Long enough for a real capture
#: on a slow connection, short enough that a stolen nonce is near-useless.
CHALLENGE_TTL_SECONDS = 120

VERIFIED_CAPTURE = "VERIFIED_CAPTURE"
ALTERED = "ALTERED"
UNVERIFIED = "UNVERIFIED"


def media_hash(data):
    """SHA-256 of the media itself.

    Hashing happens on the device. The media never has to reach Veridact for a
    manifest to exist, which matters for footage nobody wants to upload.
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def signing_message(media_hash_hex, challenge, captured_at):
    """The exact string a device signs.

    All three parts are inside the signature. Leaving the challenge out would
    make every signature replayable; leaving the timestamp out would let a real
    capture be re-attested later as if it were new.
    """
    return f"{media_hash_hex}|{challenge}|{captured_at}"


def _now():
    return datetime.now(timezone.utc)


def utc_now():
    return _now().isoformat()


class Challenge:
    """A one-time freshness nonce."""

    __slots__ = ("nonce", "issued_at", "used_at")

    def __init__(self, nonce, issued_at):
        self.nonce = nonce
        self.issued_at = issued_at
        self.used_at = None

    @property
    def is_used(self):
        return self.used_at is not None

    def is_expired(self, now=None):
        issued = datetime.fromisoformat(self.issued_at)
        return (now or _now()) - issued > timedelta(seconds=CHALLENGE_TTL_SECONDS)


class Device:
    """An enrolled capture device, identified by its **public** key.

    Veridact stores no private keys. That is not a precaution, it is the
    architecture: an operator who cannot forge a signature cannot be pressured
    into forging one, and a breach leaks nothing that lets anyone else either.
    """

    __slots__ = ("handle", "public_key", "algorithm", "enrolled_at")

    def __init__(self, handle, public_key, algorithm, enrolled_at):
        self.handle = handle
        self.public_key = public_key
        self.algorithm = algorithm
        self.enrolled_at = enrolled_at

    def describe(self):
        return f"{self.handle} ({self.algorithm})"


class Manifest:
    """A device's signed statement: *I captured this, at this time.*"""

    __slots__ = ("manifest_id", "device_handle", "media_hash", "label",
                 "challenge", "captured_at", "received_at", "algorithm", "signature")

    def __init__(self, manifest_id, device_handle, media_hash, label, challenge,
                 captured_at, received_at, algorithm, signature):
        self.manifest_id = manifest_id
        self.device_handle = device_handle
        self.media_hash = media_hash
        self.label = label
        self.challenge = challenge
        self.captured_at = captured_at
        self.received_at = received_at
        self.algorithm = algorithm
        self.signature = signature

    def message(self):
        return signing_message(self.media_hash, self.challenge, self.captured_at)

    def describe(self):
        return f"{self.label} by {self.device_handle} ({self.manifest_id})"


class Verdict:
    """What Veridact can prove about a file, and how confident it is.

    Three outcomes, never four. There is deliberately no `FAKE` — Veridact has
    no way to establish that, and offering the word would invite people to read
    `UNVERIFIED` as an accusation. Most honest media in the world is
    unverified; that is a statement about tooling, not about truth.
    """

    __slots__ = ("status", "manifest", "device", "reason", "checks")

    def __init__(self, status, reason, manifest=None, device=None, checks=None):
        self.status = status
        self.reason = reason
        self.manifest = manifest
        self.device = device
        self.checks = checks or {}

    @property
    def is_verified(self):
        return self.status == VERIFIED_CAPTURE

    def describe(self):
        return f"{self.status}: {self.reason}"

    def summary(self):
        return {
            "status": self.status,
            "reason": self.reason,
            "device": self.device.handle if self.device else None,
            "manifest": self.manifest.manifest_id if self.manifest else None,
            "checks": self.checks,
        }

    def __repr__(self):
        return f"<Verdict {self.status}>"


# --------------------------------------------------------------------------
# Signature backends
# --------------------------------------------------------------------------

class Signer:
    """A signature scheme Veridact can check.

    An interface rather than a hard-coded algorithm, because the app already
    supports two (Schnorr and ECDSA P-256) and a manifest records which one
    signed it — so a manifest stays verifiable even after the default changes.
    Pinning one algorithm into the verifier would silently orphan old manifests.
    """

    name = "abstract"

    def verify(self, public_key, message, signature):
        raise NotImplementedError


class HMACSigner(Signer):
    """A symmetric scheme for **testing only**.

    Deliberately named for what it is. Symmetric signing means the verifier
    holds the same secret the signer does and could therefore forge — exactly
    the property Veridact exists to avoid. It is here so the engine's logic can
    be tested without a key-generation dependency, and `is_asymmetric` is False
    so nothing can mistake it for production-grade.
    """

    name = "hmac-test"
    is_asymmetric = False

    def sign(self, secret, message):
        return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

    def verify(self, public_key, message, signature):
        expected = self.sign(public_key, message)
        return hmac.compare_digest(expected, signature or "")


class ECDSASigner(Signer):
    """NIST P-256 — the peer-reviewed option the app made its default.

    Genuinely asymmetric: verification needs only the public key. Requires the
    `cryptography` package, and says so plainly when it is missing rather than
    failing in a way that looks like a bad signature.
    """

    name = "ecdsa-p256"
    is_asymmetric = True

    @staticmethod
    def available():
        try:
            import cryptography  # noqa: F401
            return True
        except ImportError:
            return False

    def verify(self, public_key, message, signature):
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec, utils

        try:
            point = bytes.fromhex(public_key)
            raw = bytes.fromhex(signature)
        except ValueError:
            return False
        if len(raw) != 64:
            return False

        try:
            key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), point)
            r = int.from_bytes(raw[:32], "big")
            s = int.from_bytes(raw[32:], "big")
            key.verify(utils.encode_dss_signature(r, s),
                       message.encode(), ec.ECDSA(hashes.SHA256()))
            return True
        except (InvalidSignature, ValueError):
            return False


SIGNERS = {s.name: s() for s in (HMACSigner, ECDSASigner)}


def new_challenge():
    return Challenge(secrets.token_hex(16), utc_now())
