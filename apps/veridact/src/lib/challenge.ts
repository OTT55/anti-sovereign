import { randomBytes } from "node:crypto";
import { eq } from "drizzle-orm";
import { db } from "@/db";
import { captureChallenges, manifests } from "@/db/schema";

const CHALLENGE_TTL_MS = 120_000;

async function generateUniqueManifestId(): Promise<string> {
  for (let attempt = 0; attempt < 10; attempt++) {
    const candidate = `VD-${randomBytes(4).toString("hex").toUpperCase()}`;
    const existing = await db
      .select({ id: manifests.id })
      .from(manifests)
      .where(eq(manifests.manifestId, candidate))
      .get();
    if (!existing) return candidate;
  }
  throw new Error("failed to allocate a unique manifest id");
}

export interface IssuedChallenge {
  nonce: string;
  manifestId: string;
  expiresAt: string;
}

/** Issues a one-time nonce (120s TTL) and reserves a manifest ID for the eventual attestation. */
export async function issueChallenge(): Promise<IssuedChallenge> {
  const nonce = randomBytes(16).toString("hex");
  const expiresAt = new Date(Date.now() + CHALLENGE_TTL_MS).toISOString();
  await db.insert(captureChallenges).values({ nonce, expiresAt });
  const manifestId = await generateUniqueManifestId();
  return { nonce, manifestId, expiresAt };
}

export type ChallengeConsumeResult = { ok: true } | { ok: false; reason: "not_found" | "expired" | "already_used" };

/**
 * Burns a nonce on first use — even if the caller's signature later turns out
 * to be invalid, the nonce can never be replayed or pre-computed against.
 */
export async function consumeChallenge(nonce: string): Promise<ChallengeConsumeResult> {
  const record = await db.select().from(captureChallenges).where(eq(captureChallenges.nonce, nonce)).get();
  if (!record) return { ok: false, reason: "not_found" };
  if (record.usedAt) return { ok: false, reason: "already_used" };

  await db
    .update(captureChallenges)
    .set({ usedAt: new Date().toISOString() })
    .where(eq(captureChallenges.nonce, nonce));

  if (new Date(record.expiresAt).getTime() < Date.now()) {
    return { ok: false, reason: "expired" };
  }
  return { ok: true };
}
