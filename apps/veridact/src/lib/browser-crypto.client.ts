const KEY_ALGORITHM = { name: "ECDSA", namedCurve: "P-256" } as const;

/** Private key is non-extractable — it never leaves this browser session, even in principle. */
export async function generateDeviceKeyPair(): Promise<CryptoKeyPair> {
  return crypto.subtle.generateKey(KEY_ALGORITHM, false, ["sign", "verify"]) as Promise<CryptoKeyPair>;
}

export async function exportPublicKeySpkiBase64(publicKey: CryptoKey): Promise<string> {
  const der = await crypto.subtle.exportKey("spki", publicKey);
  return Buffer.from(der).toString("base64");
}

export async function signMessage(privateKey: CryptoKey, message: string): Promise<string> {
  const data = new TextEncoder().encode(message);
  const signature = await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, privateKey, data);
  return Buffer.from(signature).toString("base64");
}

export async function sha256HexOfBlob(blob: Blob): Promise<string> {
  const buffer = await blob.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}
