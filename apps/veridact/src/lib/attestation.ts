import { createHash } from "node:crypto";
import { eq } from "drizzle-orm";
import { db } from "@/db";
import { devices, manifests } from "@/db/schema";
import { consumeChallenge } from "./challenge";
import { canonicalCaptureMessage, verifyEcdsaSignature } from "./ecdsa";
import type { attestRequestSchema, enrollRequestSchema } from "./schemas";
import { decodeWatermark } from "./watermark";
import type { z } from "zod";

export class DeviceExistsError extends Error {}
export class DeviceNotFoundError extends Error {}

export async function enrollDevice(input: z.infer<typeof enrollRequestSchema>) {
  const existing = await db.select({ id: devices.id }).from(devices).where(eq(devices.handle, input.handle)).get();
  if (existing) {
    throw new DeviceExistsError(`handle "${input.handle}" is already enrolled`);
  }
  return db
    .insert(devices)
    .values({ handle: input.handle, publicKeySpki: input.publicKeySpki })
    .returning()
    .get();
}

export type AttestResult =
  | { ok: true; manifestId: string }
  | { ok: false; reason: "device_not_found" | "challenge_not_found" | "challenge_expired" | "challenge_used" | "signature_invalid" };

export async function attestCapture(input: z.infer<typeof attestRequestSchema>): Promise<AttestResult> {
  const device = await db.select().from(devices).where(eq(devices.handle, input.handle)).get();
  if (!device) return { ok: false, reason: "device_not_found" };

  const challengeResult = await consumeChallenge(input.challenge);
  if (!challengeResult.ok) {
    return {
      ok: false,
      reason: challengeResult.reason === "not_found" ? "challenge_not_found" : challengeResult.reason === "expired" ? "challenge_expired" : "challenge_used",
    };
  }

  const message = canonicalCaptureMessage({
    mediaHash: input.mediaHash,
    capturedAt: input.capturedAt,
    handle: input.handle,
    challenge: input.challenge,
  });
  const valid = await verifyEcdsaSignature(device.publicKeySpki, message, input.signature);
  if (!valid) return { ok: false, reason: "signature_invalid" };

  await db.insert(manifests).values({
    manifestId: input.manifestId,
    deviceId: device.id,
    mediaHash: input.mediaHash,
    label: input.label ?? null,
    challenge: input.challenge,
    signature: input.signature,
    capturedAt: input.capturedAt,
    watermarkSecret: input.watermarkSecret ?? null,
  });

  return { ok: true, manifestId: input.manifestId };
}

export type VerifyVerdict = "VERIFIED_CAPTURE" | "SIGNATURE_INVALID" | "RECOMPRESSED" | "ALTERED" | "UNVERIFIED";

export interface VerifyResult {
  verdict: VerifyVerdict;
  manifestId?: string;
  handle?: string;
  capturedAt?: string;
  label?: string | null;
}

/**
 * The same hash/watermark/manifest-reference cascade as the legacy product:
 * exact hash match re-verifies the signature; failing that, a decoded
 * watermark proves the pixels trace back to a real capture even though the
 * bytes changed; failing that, a referenced manifest with a mismatched hash
 * means the file was altered; otherwise it's simply unverified.
 */
export async function verifyMedia(fileHash: string, imageBuffer: Buffer | null, referencedManifestId?: string): Promise<VerifyResult> {
  const exact = await db.select().from(manifests).where(eq(manifests.mediaHash, fileHash)).get();
  if (exact) {
    const device = await db.select().from(devices).where(eq(devices.id, exact.deviceId)).get();
    const message = canonicalCaptureMessage({
      mediaHash: exact.mediaHash,
      capturedAt: exact.capturedAt,
      handle: device!.handle,
      challenge: exact.challenge,
    });
    const signatureValid = await verifyEcdsaSignature(device!.publicKeySpki, message, exact.signature);
    return {
      verdict: signatureValid ? "VERIFIED_CAPTURE" : "SIGNATURE_INVALID",
      manifestId: exact.manifestId,
      handle: device!.handle,
      capturedAt: exact.capturedAt,
      label: exact.label,
    };
  }

  if (imageBuffer) {
    const decoded = await decodeWatermark(imageBuffer);
    if (decoded) {
      const byWatermark = await db.select().from(manifests).where(eq(manifests.watermarkSecret, decoded)).get();
      if (byWatermark) {
        const device = await db.select().from(devices).where(eq(devices.id, byWatermark.deviceId)).get();
        return {
          verdict: "RECOMPRESSED",
          manifestId: byWatermark.manifestId,
          handle: device?.handle,
          capturedAt: byWatermark.capturedAt,
          label: byWatermark.label,
        };
      }
    }
  }

  if (referencedManifestId) {
    const referenced = await db.select().from(manifests).where(eq(manifests.manifestId, referencedManifestId)).get();
    if (referenced && referenced.mediaHash !== fileHash) {
      return { verdict: "ALTERED", manifestId: referenced.manifestId };
    }
  }

  return { verdict: "UNVERIFIED" };
}

export function sha256HexOfBuffer(buffer: Buffer): string {
  return createHash("sha256").update(buffer).digest("hex");
}

export async function getStats() {
  const deviceRows = await db.select({ id: devices.id }).from(devices);
  const manifestRows = await db.select({ id: manifests.id }).from(manifests);
  return { deviceCount: deviceRows.length, manifestCount: manifestRows.length };
}
