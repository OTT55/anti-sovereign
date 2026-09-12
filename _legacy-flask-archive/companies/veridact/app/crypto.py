"""
The crypto core: verifying Schnorr signatures made by capture devices.

Veridact only ever *verifies* — it holds public keys, never private keys, so it
can confirm a device signed something but can never forge a signature
(decisions/0002). Same 2048-bit MODP group (RFC 3526, group 14) proven in the
Nullform build.

A device signs a manifest message `m` as (t, s); we accept it iff
    gˢ ≡ t · yᶜ (mod p),  where  c = H(g, y, t, m)
which holds only if the signer knew the private key behind public key y.

`manifest_message`, `challenge`, and this verification MUST match the browser's
signing code in static/device.js byte for byte.
"""

import hashlib

# RFC 3526, 2048-bit MODP group (id 14). Generator g = 2.
P_HEX = (
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D"
    "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D"
    "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9"
    "DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
    "15728E5A8AACAA68FFFFFFFFFFFFFFFF"
)
P = int(P_HEX, 16)
G = 2
Q = P - 1  # exponents reduce mod (P-1)


def manifest_message(media_hash: str, captured_at: str, handle: str,
                     challenge: str) -> str:
    """Canonical string a device signs. Must match static/device.js exactly.

    `challenge` is the one-time nonce Veridact issued just before the capture. It
    is what makes the signature provably live: without it a signature could be
    pre-computed or replayed (decisions/0003).
    """
    return f"{media_hash}|{captured_at}|{handle}|{challenge}"


def challenge(y: int, t: int, message: str) -> int:
    material = f"{G}|{y}|{t}|{message}".encode()
    return int(hashlib.sha256(material).hexdigest(), 16) % Q


def verify_signature(public_key: int, t: int, s: int, message: str) -> bool:
    if not (1 <= t < P) or not (0 <= s < Q):
        return False
    c = challenge(public_key, t, message)
    return pow(G, s, P) == (t * pow(public_key, c, P)) % P
