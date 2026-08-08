// Veridact ECDSA P-256 device cryptography (decisions/0004) — the
// peer-reviewed alternative to the custom Schnorr scheme in device.js.
//
// Uses the browser's native Web Crypto API — no hand-rolled math, no
// BigInt arithmetic, no custom group. This is deliberately the opposite
// style of device.js: there, we implement Schnorr ourselves because no
// standard primitive matched; here, we use the standard primitive directly.
//
// `sha256Hex` and `manifestMessage` are shared with device.js (loaded first
// on every page) — the message format is identical across both schemes, so a
// manifest's meaning doesn't depend on which algorithm signed it.

const ECDSA_PARAMS = { name: "ECDSA", namedCurve: "P-256" };

function bufToHex(buf) {
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("");
}
function hexToBuf(hex) {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < bytes.length; i++) bytes[i] = parseInt(hex.substr(i * 2, 2), 16);
  return bytes.buffer;
}

// Generate a device keypair. The private key is extractable in this build so
// it can be saved and reused across sessions, mirroring device.js's UX
// (decisions/0004 §6 notes that `extractable: false`, or WebAuthn, is the
// stronger production direction — this keeps today's save-your-key flow
// consistent between both signing options rather than making ECDSA behave
// unexpectedly differently).
async function generateEcdsaDeviceKey() {
  const pair = await crypto.subtle.generateKey(ECDSA_PARAMS, true, ["sign", "verify"]);
  const pubRaw = await crypto.subtle.exportKey("raw", pair.publicKey);
  const privJwk = await crypto.subtle.exportKey("jwk", pair.privateKey);
  return {
    privateKey: JSON.stringify(privJwk),   // save this — never sent to the server
    publicKey: bufToHex(pubRaw),           // this is what gets enrolled
  };
}

async function importEcdsaPrivateKey(privateKeyStr) {
  const jwk = JSON.parse(privateKeyStr);
  return crypto.subtle.importKey("jwk", jwk, ECDSA_PARAMS, false, ["sign"]);
}

// Sign a manifest message -> a single raw hex signature (r‖s, 64 bytes for
// P-256). The server converts this to DER before verifying — see
// app/crypto_ecdsa.py for why, and where that was proven correct against a
// real Web Crypto signature before being relied on.
async function signManifestEcdsa(privateKeyStr, message) {
  const key = await importEcdsaPrivateKey(privateKeyStr);
  return signManifestEcdsaWithKey(key, message);
}

// --- decisions/0008: store the key, don't make the user hold it ---
//
// Everything above this line is unchanged (decisions/0004) and stays in
// place only as the *import* path for a key someone saved before this
// change existed (see keystore.js / authenticate.js "import a saved key").
// New enrolments use the functions below instead.

// Generate a device keypair whose PRIVATE key is non-extractable: once
// created, no code on this page (or any other) can ever read its raw bytes
// back out via exportKey — it can only be used to sign. The CryptoKey object
// itself is what gets stored (in IndexedDB, via keystore.js), not a text
// export of it. The public key is unaffected — public keys are meant to be
// shared, so it's exported as raw bytes exactly as before.
async function generateEcdsaDeviceKeyStored() {
  const pair = await crypto.subtle.generateKey(ECDSA_PARAMS, false, ["sign"]);
  const pubRaw = await crypto.subtle.exportKey("raw", pair.publicKey);
  return { cryptoKey: pair.privateKey, publicKey: bufToHex(pubRaw) };
}

// Sign directly with an already-available CryptoKey (fetched from IndexedDB,
// or freshly generated) — no JWK parsing, no text ever touches this function.
async function signManifestEcdsaWithKey(cryptoKey, message) {
  const sig = await crypto.subtle.sign(
    { name: "ECDSA", hash: "SHA-256" }, cryptoKey, new TextEncoder().encode(message)
  );
  return { t: bufToHex(sig), s: "" };
}
