"""
Write a real C2PA manifest into a capture, using the same official
`c2pa-python` library `app/c2pa_check.py` already uses to read them — the
"write" half of decisions/0007's interop story (decisions/0010).

Two things this module is honest about, not silent on:

1. Veridact signs with its OWN self-signed certificate, generated once and
   reused (not the library's bundled test-fixture cert, and not regenerated
   every restart — a stable identity matters here even though nothing about
   this makes the manifest "Trusted" by third parties; see decisions/0010).
   A self-signed cert produces a genuinely valid, correctly-signed manifest —
   `signingCredential.untrusted` in a reader's validation_status is expected
   and correct until Veridact's cert is on an actual C2PA trust list, which
   is a registration process this code cannot complete by itself.
2. This embeds metadata into the file's container (JUMBF), which changes the
   file's bytes — exactly like decisions/0009's watermark, this MUST happen
   before hashing/signing Veridact's own manifest, never after, or a fresh
   capture could never hash-match what was signed (the same bug caught and
   fixed there).
"""

import datetime
import os
import tempfile
import threading

import c2pa
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

# A real, public timestamp authority — required, not optional: signing fails
# with an opaque "empty string" error without one (verified against this
# exact library version before relying on it, decisions/0010). Same one the
# library's own official example uses.
_TSA_URL = "http://timestamp.digicert.com"

_CERT_DIR = os.path.join(os.path.dirname(__file__), "..", "c2pa_signing")
_CERT_PATH = os.path.join(_CERT_DIR, "veridact_cert.pem")
_KEY_PATH = os.path.join(_CERT_DIR, "veridact_key.pem")

_signer = None
_signer_lock = threading.Lock()


def _generate_self_signed_cert() -> tuple[bytes, bytes]:
    """A stable, self-signed identity for Veridact — generated once and
    reused across restarts (unlike the ad-hoc TLS cert in decisions/0005,
    regenerating this every run would make every capture look like it came
    from a different signer, which is needlessly incoherent even though
    none of them are "Trusted" by a third party yet either way)."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Veridact"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Veridact"),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    # Extensions mirror the official C2PA test fixture's shape (verified
    # against contentauth/c2pa-python's tests/fixtures/es256_certs.pem) —
    # a self-signed cert missing SubjectKeyIdentifier was rejected outright
    # ("the certificate is invalid") before this was added.
    ski = x509.SubjectKeyIdentifier.from_public_key(key.public_key())
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365 * 5))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=True,
                key_encipherment=False, data_encipherment=False,
                key_agreement=False, key_cert_sign=False, crl_sign=False,
                encipher_only=False, decipher_only=False,
            ), critical=True,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.EMAIL_PROTECTION]), critical=True)
        .add_extension(ski, critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(ski), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return cert_pem, key_pem


def _signer_instance() -> "c2pa.Signer":
    global _signer
    if _signer is None:
        with _signer_lock:
            if _signer is None:
                os.makedirs(_CERT_DIR, exist_ok=True)
                if not (os.path.exists(_CERT_PATH) and os.path.exists(_KEY_PATH)):
                    cert_pem, key_pem = _generate_self_signed_cert()
                    with open(_CERT_PATH, "wb") as fh:
                        fh.write(cert_pem)
                    with open(_KEY_PATH, "wb") as fh:
                        fh.write(key_pem)
                with open(_CERT_PATH, "rb") as fh:
                    cert_pem = fh.read()
                with open(_KEY_PATH, "rb") as fh:
                    key_pem = fh.read()
                info = c2pa.C2paSignerInfo(
                    c2pa.C2paSigningAlg.ES256, cert_pem, key_pem, _TSA_URL,
                )
                _signer = c2pa.Signer.from_info(info)
    return _signer


def embed_manifest(image_bytes: bytes, *, device_handle: str, captured_at: str,
                    challenge: str) -> bytes:
    """Build and embed a C2PA manifest into `image_bytes` (a PNG), signed
    with Veridact's own certificate. Assertions cover exactly what the
    capture flow actually established — nothing more (decisions/0010):
    the standard c2pa.actions "created, digital capture" action, plus a
    Veridact-specific assertion carrying the capture timestamp, the
    enrolled device handle, and the one-time freshness-challenge response
    that proves this was live (decisions/0003).
    """
    manifest = {
        "claim_generator_info": [{"name": "Veridact", "version": "0.1.0"}],
        "format": "image/png",
        "title": "Veridact capture",
        "ingredients": [],
        "assertions": [
            {
                "label": "c2pa.actions",
                "data": {"actions": [{
                    "action": "c2pa.created",
                    "digitalSourceType": "http://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture",
                }]},
            },
            {
                "label": "veridact.capture",
                "data": {
                    "captured_at": captured_at,
                    "device": device_handle,
                    "challenge": challenge,
                },
            },
        ],
    }

    builder = c2pa.Builder(manifest)
    fd_src, src_path = tempfile.mkstemp(suffix=".png")
    fd_dst, dst_path = tempfile.mkstemp(suffix=".png")
    os.close(fd_dst)  # sign_file opens dest itself; just needed a unique path
    try:
        with os.fdopen(fd_src, "wb") as fh:
            fh.write(image_bytes)
        builder.sign_file(src_path, dst_path, _signer_instance())
        with open(dst_path, "rb") as fh:
            return fh.read()
    finally:
        os.remove(src_path)
        os.remove(dst_path)
