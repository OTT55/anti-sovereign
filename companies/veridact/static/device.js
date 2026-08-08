// Veridact capture-device cryptography — runs in the browser.
// The device's private key is generated and used HERE and never sent anywhere.
// Veridact only ever receives the public key and signatures. Same 2048-bit MODP
// group as the server (app/crypto.py); VD_P_HEX and VD_G are injected by the page.

const P = BigInt("0x" + window.VD_P_HEX);
const G = BigInt(window.VD_G);
const Q = P - 1n;

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

function randScalar() {
  const bytes = new Uint8Array(256);
  crypto.getRandomValues(bytes);
  let n = 0n;
  for (const b of bytes) n = (n << 8n) | BigInt(b);
  return (n % (Q - 1n)) + 1n;
}

// SHA-256 of raw bytes -> hex. Used to fingerprint a media file locally.
async function sha256Hex(buffer) {
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, "0")).join("");
}
const sha256File = async (file) => sha256Hex(await file.arrayBuffer());

// The canonical string a device signs — MUST match app/crypto.manifest_message.
// `challenge` is the one-time nonce Veridact issued for this capture; it proves
// the signature was made live and can't be replayed (decisions/0003).
const manifestMessage = (mediaHash, capturedAt, handle, challenge) =>
  `${mediaHash}|${capturedAt}|${handle}|${challenge}`;

// Fiat–Shamir challenge — MUST match app/crypto.challenge.
async function challenge(y, t, message) {
  const material = `${G}|${y}|${t}|${message}`;
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(material));
  const hex = [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, "0")).join("");
  return BigInt("0x" + hex) % Q;
}

// Generate a device keypair. x is the private key; y = g^x mod p is public.
function generateDeviceKey() {
  const x = randScalar();
  return { privateKey: x.toString(), publicKey: modpow(G, x, P).toString() };
}

// Sign a manifest message with the device's private key -> Schnorr signature (t, s).
async function signManifest(privateKeyStr, message) {
  const x = BigInt(privateKeyStr);
  const r = randScalar();
  const t = modpow(G, r, P);
  const c = await challenge(modpow(G, x, P), t, message);
  const s = (r + c * x) % Q;
  return { t: t.toString(), s: s.toString() };
}
