import { describe, expect, it } from "vitest";
import { canonicalCaptureMessage, verifyEcdsaSignature } from "./ecdsa";

async function generateTestDevice() {
  const keyPair = (await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, [
    "sign",
    "verify",
  ])) as CryptoKeyPair;
  const spki = await crypto.subtle.exportKey("spki", keyPair.publicKey);
  const publicKeySpki = Buffer.from(spki).toString("base64");
  return { keyPair, publicKeySpki };
}

async function sign(privateKey: CryptoKey, message: string): Promise<string> {
  const data = new TextEncoder().encode(message);
  const sig = await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, privateKey, data);
  return Buffer.from(sig).toString("base64");
}

describe("ECDSA capture attestation", () => {
  it("verifies a signature produced by the matching private key", async () => {
    const { keyPair, publicKeySpki } = await generateTestDevice();
    const message = canonicalCaptureMessage({
      mediaHash: "a".repeat(64),
      capturedAt: "2026-01-01T00:00:00.000Z",
      handle: "alice",
      challenge: "deadbeef".repeat(4),
    });
    const signature = await sign(keyPair.privateKey, message);
    expect(await verifyEcdsaSignature(publicKeySpki, message, signature)).toBe(true);
  });

  it("rejects a signature from a different device's key", async () => {
    const { publicKeySpki } = await generateTestDevice();
    const impostor = await generateTestDevice();
    const message = canonicalCaptureMessage({
      mediaHash: "a".repeat(64),
      capturedAt: "2026-01-01T00:00:00.000Z",
      handle: "alice",
      challenge: "deadbeef".repeat(4),
    });
    const signature = await sign(impostor.keyPair.privateKey, message);
    expect(await verifyEcdsaSignature(publicKeySpki, message, signature)).toBe(false);
  });

  it("rejects a valid signature over a tampered message (e.g. swapped challenge)", async () => {
    const { keyPair, publicKeySpki } = await generateTestDevice();
    const original = canonicalCaptureMessage({
      mediaHash: "a".repeat(64),
      capturedAt: "2026-01-01T00:00:00.000Z",
      handle: "alice",
      challenge: "deadbeef".repeat(4),
    });
    const signature = await sign(keyPair.privateKey, original);
    const tampered = canonicalCaptureMessage({
      mediaHash: "b".repeat(64),
      capturedAt: "2026-01-01T00:00:00.000Z",
      handle: "alice",
      challenge: "deadbeef".repeat(4),
    });
    expect(await verifyEcdsaSignature(publicKeySpki, tampered, signature)).toBe(false);
  });
});
