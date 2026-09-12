"""Veridact: proving a capture, and refusing to overclaim.

Tested against **real ECDSA P-256 keys**, not a stand-in — the security
property is that verification needs only the public key, and a symmetric
stub cannot demonstrate that.
"""

from datetime import datetime, timedelta, timezone

import pytest

from veridact_engine import (
    ALTERED, CHALLENGE_TTL_SECONDS, UNVERIFIED, VERIFIED_CAPTURE,
    AttestationError, ECDSASigner, EnrolmentError, Veridact, media_hash,
    signing_message,
)

pytestmark = pytest.mark.skipif(
    not ECDSASigner.available(), reason="cryptography not installed")

FOOTAGE = b"\x00\x01raw camera footage bytes\xff"


def _keypair():
    """A real P-256 keypair. The private key never enters the registry."""
    from cryptography.hazmat.primitives.asymmetric import ec
    private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key().public_bytes(
        encoding=__import__("cryptography.hazmat.primitives.serialization",
                            fromlist=["Encoding"]).Encoding.X962,
        format=__import__("cryptography.hazmat.primitives.serialization",
                          fromlist=["PublicFormat"]).PublicFormat.UncompressedPoint,
    )
    return private, public.hex()


def _sign(private, message):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, utils
    der = private.sign(message.encode(), ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(der)
    return (r.to_bytes(32, "big") + s.to_bytes(32, "big")).hex()


@pytest.fixture
def registry():
    return Veridact()


@pytest.fixture
def device(registry):
    private, public = _keypair()
    registry.enrol("ott-pixel-8", public, algorithm="ecdsa-p256")
    return private, public


def _capture(registry, private, data=FOOTAGE, label="street interview",
             captured_at="2026-08-02T10:00:00+00:00"):
    digest = media_hash(data)
    challenge = registry.issue_challenge()
    signature = _sign(private, signing_message(digest, challenge.nonce, captured_at))
    manifest = registry.attest("ott-pixel-8", digest, label,
                               challenge.nonce, captured_at, signature)
    return digest, manifest


# -- the happy path --------------------------------------------------------

def test_a_real_capture_verifies(registry, device):
    private, _public = device
    digest, _manifest = _capture(registry, private)

    verdict = registry.verify(digest)
    assert verdict.status == VERIFIED_CAPTURE
    assert verdict.is_verified
    assert all(verdict.checks.values())


def test_verification_needs_only_the_public_key(registry, device):
    """The property the whole product rests on. Veridact never holds a private
    key, so it cannot forge — and cannot be made to."""
    private, public = device
    digest, _ = _capture(registry, private)

    fresh = Veridact()
    fresh.enrol("ott-pixel-8", public, algorithm="ecdsa-p256")
    # Re-attesting into the fresh registry uses only what a verifier would have.
    challenge = fresh.issue_challenge()
    signature = _sign(private, signing_message(digest, challenge.nonce, "2026-08-02T10:00:00+00:00"))
    fresh.attest("ott-pixel-8", digest, "copy", challenge.nonce,
                 "2026-08-02T10:00:00+00:00", signature)

    assert fresh.verify(digest).status == VERIFIED_CAPTURE
    assert "private" not in str(fresh.devices["ott-pixel-8"].__dict__ if hasattr(
        fresh.devices["ott-pixel-8"], "__dict__") else fresh.devices["ott-pixel-8"].public_key)


# -- tampering -------------------------------------------------------------

def test_altering_one_byte_breaks_verification(registry, device):
    """Edit a frame and the hash changes, so nothing vouches for it."""
    private, _ = device
    _capture(registry, private)

    tampered = media_hash(FOOTAGE + b"x")
    assert registry.verify(tampered).status == UNVERIFIED


def test_a_corrupted_manifest_reads_as_altered_not_unverified(registry, device):
    """Two different failures. "Never seen it" is not an accusation; "seen it
    and it no longer matches" points at the file."""
    private, _ = device
    digest, manifest = _capture(registry, private)

    manifest.captured_at = "2020-01-01T00:00:00+00:00"   # outside the signature
    verdict = registry.verify(digest)
    assert verdict.status == ALTERED
    assert verdict.checks["manifest_found"]
    assert not verdict.checks["signature_valid"]


def test_a_signature_from_the_wrong_device_is_refused(registry, device):
    _private, _ = device
    attacker, _attacker_public = _keypair()

    digest = media_hash(FOOTAGE)
    challenge = registry.issue_challenge()
    signature = _sign(attacker, signing_message(digest, challenge.nonce, "2026-08-02T10:00:00+00:00"))

    with pytest.raises(AttestationError) as e:
        registry.attest("ott-pixel-8", digest, "forged", challenge.nonce,
                        "2026-08-02T10:00:00+00:00", signature)
    assert "does not match" in str(e.value)


def test_a_rejected_attestation_is_not_stored(registry, device):
    """Storing it would later read as ALTERED and blame the file rather than
    the submission."""
    _private, _ = device
    attacker, _ = _keypair()
    digest = media_hash(FOOTAGE)
    challenge = registry.issue_challenge()

    with pytest.raises(AttestationError):
        registry.attest("ott-pixel-8", digest, "forged", challenge.nonce,
                        "2026-08-02T10:00:00+00:00", _sign(attacker, "anything"))

    assert registry.verify(digest).status == UNVERIFIED
    assert registry.manifests == {}


# -- replay ----------------------------------------------------------------

def test_a_challenge_cannot_be_used_twice(registry, device):
    """Without this a signature could be computed once and replayed forever."""
    private, _ = device
    digest = media_hash(FOOTAGE)
    challenge = registry.issue_challenge()
    signature = _sign(private, signing_message(digest, challenge.nonce, "2026-08-02T10:00:00+00:00"))

    registry.attest("ott-pixel-8", digest, "first", challenge.nonce,
                    "2026-08-02T10:00:00+00:00", signature)

    with pytest.raises(AttestationError) as e:
        registry.attest("ott-pixel-8", digest, "replay", challenge.nonce,
                        "2026-08-02T10:00:00+00:00", signature)
    assert "already been used" in str(e.value)


def test_an_expired_challenge_is_refused():
    """A stolen nonce must not be hoardable."""
    clock = {"now": datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc)}
    registry = Veridact(clock=lambda: clock["now"])
    private, public = _keypair()
    registry.enrol("ott-pixel-8", public, algorithm="ecdsa-p256")

    challenge = registry.issue_challenge()
    clock["now"] += timedelta(seconds=CHALLENGE_TTL_SECONDS + 5)

    digest = media_hash(FOOTAGE)
    signature = _sign(private, signing_message(digest, challenge.nonce, "2026-08-02T10:00:00+00:00"))
    with pytest.raises(AttestationError) as e:
        registry.attest("ott-pixel-8", digest, "late", challenge.nonce,
                        "2026-08-02T10:00:00+00:00", signature)
    assert "expired" in str(e.value)


def test_an_unknown_challenge_is_refused(registry, device):
    private, _ = device
    digest = media_hash(FOOTAGE)
    with pytest.raises(AttestationError):
        registry.attest("ott-pixel-8", digest, "no challenge", "made-up-nonce",
                        "2026-08-02T10:00:00+00:00", _sign(private, "x"))


# -- it never says "fake" --------------------------------------------------

def test_unattested_media_is_unverified_not_fake(registry, device):
    """Most honest media in the world has never been attested. Saying "fake"
    would be a lie about what Veridact knows."""
    verdict = registry.verify(media_hash(b"someone else's holiday video"))
    assert verdict.status == UNVERIFIED
    assert "not a claim it is fake" in verdict.reason


def test_there_is_no_fake_verdict_at_all():
    """Not a policy — the value does not exist to be returned."""
    import veridact_engine
    assert not hasattr(veridact_engine, "FAKE")
    assert "FAKE" not in {VERIFIED_CAPTURE, ALTERED, UNVERIFIED}


# -- enrolment and revocation ----------------------------------------------

def test_an_unknown_algorithm_is_refused_at_enrolment(registry):
    """A device enrolled under an unverifiable scheme returns UNVERIFIED
    forever, silently."""
    with pytest.raises(EnrolmentError) as e:
        registry.enrol("odd-device", "deadbeef", algorithm="rot13")
    assert "Unknown algorithm" in str(e.value)


def test_a_handle_cannot_be_enrolled_twice(registry, device):
    _private, public = device
    with pytest.raises(EnrolmentError):
        registry.enrol("ott-pixel-8", public)


def test_attesting_from_an_unenrolled_device_is_refused(registry):
    with pytest.raises(AttestationError):
        registry.attest("nobody", media_hash(FOOTAGE), "x", "nonce",
                        "2026-08-02T10:00:00+00:00", "sig")


def test_revoking_a_device_degrades_to_unverified_not_altered(registry, device):
    """The claim still exists; it just can no longer be checked. Calling that
    ALTERED would accuse the file of something it did not do."""
    private, _ = device
    digest, _manifest = _capture(registry, private)
    assert registry.verify(digest).status == VERIFIED_CAPTURE

    registry.revoke("ott-pixel-8")
    verdict = registry.verify(digest)
    assert verdict.status == UNVERIFIED
    assert "no longer enrolled" in verdict.reason


def test_revoking_keeps_the_manifests(registry, device):
    """Deleting them would erase the record that a capture was ever attested."""
    private, _ = device
    _capture(registry, private)
    registry.revoke("ott-pixel-8")
    assert registry.manifests


# -- housekeeping ----------------------------------------------------------

def test_the_media_never_has_to_travel(registry, device):
    """Only the hash is needed, which matters for footage nobody wants to
    upload."""
    private, _ = device
    digest, _ = _capture(registry, private)
    assert registry.verify(digest).is_verified
    assert len(digest) == 64


def test_a_verdict_summarises_what_it_checked(registry, device):
    private, _ = device
    digest, _ = _capture(registry, private)
    summary = registry.verify(digest).summary()
    assert summary["status"] == VERIFIED_CAPTURE
    assert summary["device"] == "ott-pixel-8"
    assert summary["checks"]["signature_valid"]


def test_verification_is_deterministic(registry, device):
    private, _ = device
    digest, _ = _capture(registry, private)
    assert registry.verify(digest).summary() == registry.verify(digest).summary()
