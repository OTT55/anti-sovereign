// Nullform client-side cryptography.
// The private key and every random nonce are generated and used HERE, in the
// browser. Only public values (public key, and the proof pair t, s) are ever
// sent to the server. NF_P_HEX and NF_G are injected by the page template.

const P = BigInt("0x" + window.NF_P_HEX);
const G = BigInt(window.NF_G);
const Q = P - 1n; // exponents reduce mod (P-1)

function modpow(base, exp, mod) {
  base %= mod;
  let result = 1n;
  while (exp > 0n) {
    if (exp & 1n) result = (result * base) % mod;
    base = (base * base) % mod;
    exp >>= 1n;
  }
  return result;
}

// A cryptographically-random BigInt in [1, Q-1].
function randScalar() {
  const bytes = new Uint8Array(256); // 2048 bits of entropy
  crypto.getRandomValues(bytes);
  let n = 0n;
  for (const b of bytes) n = (n << 8n) | BigInt(b);
  return (n % (Q - 1n)) + 1n;
}

// Fiat–Shamir challenge — MUST match the server's SHA-256 material exactly.
async function challenge(y, t, message) {
  const material = `${G}|${y}|${t}|${message}`;
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(material));
  const hex = [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, "0")).join("");
  return BigInt("0x" + hex) % Q;
}

// Generate a fresh identity keypair. x is the secret; y = g^x mod p is public.
function generateKeypair() {
  const x = randScalar();
  const y = modpow(G, x, P);
  return { x: x.toString(), y: y.toString() };
}

// Build a non-interactive Schnorr proof of knowledge of x, bound to `message`.
async function proveKnowledge(xStr, message) {
  const x = BigInt(xStr);
  const r = randScalar();
  const t = modpow(G, r, P);
  const c = await challenge(modpow(G, x, P), t, message);
  const s = (r + c * x) % Q;
  return { t: t.toString(), s: s.toString() };
}
