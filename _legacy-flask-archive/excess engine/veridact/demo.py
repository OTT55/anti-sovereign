"""What Veridact can prove, and what it refuses to claim.

    python demo.py

Real P-256 keys, real signatures. The private key is generated here to stand in
for a capture device; it never enters the registry.
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent / "src"))

from veridact_engine import (  # noqa: E402
    AttestationError, Veridact, media_hash, signing_message,
)


def head(n, title):
    print(f"\n{'─' * 70}\n{n}. {title}\n{'─' * 70}")


def keypair():
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key().public_bytes(
        encoding=Encoding.X962, format=PublicFormat.UncompressedPoint)
    return private, public.hex()


def sign(private, message):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, utils
    der = private.sign(message.encode(), ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(der)
    return (r.to_bytes(32, "big") + s.to_bytes(32, "big")).hex()


FOOTAGE = b"\x00\x01raw camera footage from a street interview\xff"
CAPTURED_AT = "2026-08-02T10:00:00+00:00"

veridact = Veridact()
private, public = keypair()

head(1, "A device enrols with its PUBLIC key")
device = veridact.enrol("ott-pixel-8", public, algorithm="ecdsa-p256")
print(f"  enrolled: {device.describe()}")
print(f"  public key stored: {public[:32]}…")
print("\n  The private key stays on the device. Veridact can check a signature")
print("  and is structurally incapable of forging one — an operator who cannot")
print("  forge cannot be pressured into forging.")

head(2, "A capture is attested")
digest = media_hash(FOOTAGE)
challenge = veridact.issue_challenge()
print(f"  media hash : {digest[:32]}…")
print(f"  challenge  : {challenge.nonce}   (one-time, expires in 120s)")

signature = sign(private, signing_message(digest, challenge.nonce, CAPTURED_AT))
manifest = veridact.attest("ott-pixel-8", digest, "street interview",
                           challenge.nonce, CAPTURED_AT, signature)
print(f"  manifest   : {manifest.describe()}")
print("\n  The signature covers the hash, the challenge AND the timestamp.")
print("  The footage itself never left the device.")

head(3, "Verifying the untouched file")
verdict = veridact.verify(digest)
print(f"  {verdict.describe()}")
print(f"  checks: {verdict.checks}")

head(4, "Verifying a file that was edited")
tampered = media_hash(FOOTAGE + b"\x00")
print(f"  {veridact.verify(tampered).describe()}")

head(5, "Verifying media nobody ever attested")
print(f"  {veridact.verify(media_hash(b'a holiday video')).describe()}")
print("\n  Note what it does NOT say. Most honest media has never been attested;")
print("  calling it fake would be a lie about what Veridact knows.")

head(6, "Replaying a signature")
try:
    veridact.attest("ott-pixel-8", digest, "replay attempt",
                    challenge.nonce, CAPTURED_AT, signature)
except AttestationError as e:
    print(f"  refused — {e}")

head(7, "A forged signature from another device")
attacker, _ = keypair()
fresh = veridact.issue_challenge()
try:
    veridact.attest("ott-pixel-8", digest, "forged", fresh.nonce, CAPTURED_AT,
                    sign(attacker, signing_message(digest, fresh.nonce, CAPTURED_AT)))
except AttestationError as e:
    print(f"  refused — {e}")

head(8, "If the device is later revoked")
veridact.revoke("ott-pixel-8")
after = veridact.verify(digest)
print(f"  {after.describe()}")
print("\n  It degrades to UNVERIFIED, not ALTERED. The claim still exists —")
print("  it just cannot be checked any more. Accusing the file would be wrong.")

print(f"\n{'─' * 70}")
print("Three verdicts, never four. There is no FAKE — the value does not exist.")
print(f"{'─' * 70}\n")
