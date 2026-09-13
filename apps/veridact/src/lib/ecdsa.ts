const KEY_ALGORITHM = { name: "ECDSA", namedCurve: "P-256" } as const;

/** Devices enroll a public key; the server only ever verifies, never signs — the private key never leaves the browser. */
export async function importDevicePublicKey(spkiBase64: string): Promise<CryptoKey> {
  const der = Buffer.from(spkiBase64, "base64");
  return crypto.subtle.importKey("spki", der, KEY_ALGORITHM, false, ["verify"]);
}

/** Signature is the raw (r||s / IEEE P1363) format Web Crypto produces, base64-encoded. */
export async function verifyEcdsaSignature(
  publicKeySpkiBase64: string,
  message: string,
  signatureBase64: string,
): Promise<boolean> {
  try {
    const key = await importDevicePublicKey(publicKeySpkiBase64);
    const signature = Buffer.from(signatureBase64, "base64");
    const data = new TextEncoder().encode(message);
    return await crypto.subtle.verify({ name: "ECDSA", hash: "SHA-256" }, key, signature, data);
  } catch {
    return false;
  }
}

/** The exact message a device must sign — folding in the challenge nonce proves freshness. */
export function canonicalCaptureMessage(fields: {
  mediaHash: string;
  capturedAt: string;
  handle: string;
  challenge: string;
}): string {
  return `${fields.mediaHash}|${fields.capturedAt}|${fields.handle}|${fields.challenge}`;
}
