import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";
import { eq } from "drizzle-orm";
import { db } from "@/db";
import { provenanceRecords, users } from "@/db/schema";
import { getSigningKey } from "./secrets";
import { recordReputationEvent } from "./credit";
import type { provenanceCreateSchema } from "./schemas";
import type { z } from "zod";

export class DuplicateHashError extends Error {}

interface SignedFields {
  registryId: string;
  contentHash: string;
  filename: string;
  ownerId: number;
  createdAt: string;
}

function sign(fields: SignedFields): string {
  const message = [fields.registryId, fields.contentHash, fields.filename, String(fields.ownerId), fields.createdAt].join("|");
  return createHmac("sha256", getSigningKey()).update(message).digest("hex");
}

export function verifyProvenanceSignature(fields: SignedFields, signature: string): boolean {
  const expected = Buffer.from(sign(fields), "hex");
  const actual = Buffer.from(signature, "hex");
  return expected.length === actual.length && timingSafeEqual(expected, actual);
}

async function generateUniqueRegistryId(): Promise<string> {
  for (let attempt = 0; attempt < 10; attempt++) {
    const candidate = `FV-${randomBytes(4).toString("hex").toUpperCase()}`;
    const existing = await db.select({ id: provenanceRecords.id }).from(provenanceRecords).where(eq(provenanceRecords.registryId, candidate)).get();
    if (!existing) return candidate;
  }
  throw new Error("failed to allocate a unique registry id");
}

export async function registerProvenance(ownerId: number, input: z.infer<typeof provenanceCreateSchema>) {
  const existing = await db.select({ registryId: provenanceRecords.registryId }).from(provenanceRecords).where(eq(provenanceRecords.contentHash, input.contentHash)).get();
  if (existing) {
    throw new DuplicateHashError(`this file is already registered as ${existing.registryId}`);
  }

  const registryId = await generateUniqueRegistryId();
  const createdAt = new Date().toISOString();
  const signature = sign({ registryId, contentHash: input.contentHash, filename: input.filename, ownerId, createdAt });

  const record = await db
    .insert(provenanceRecords)
    .values({
      registryId,
      ownerId,
      contentHash: input.contentHash,
      filename: input.filename,
      title: input.title ?? null,
      role: input.role ?? null,
      contributors: input.contributors ?? null,
      aiDisclosure: input.aiDisclosure ?? null,
      source: input.source ?? null,
      signature,
      createdAt,
    })
    .returning()
    .get();

  await recordReputationEvent({ userId: ownerId, kind: "work.registered", weight: 1, source: "framevault" });

  return record;
}

export async function verifyProvenanceByHash(contentHash: string) {
  const record = await db.select().from(provenanceRecords).where(eq(provenanceRecords.contentHash, contentHash)).get();
  if (!record) return { registered: false as const };

  const owner = await db.select({ handle: users.handle, displayName: users.displayName }).from(users).where(eq(users.id, record.ownerId)).get();
  const signatureValid = verifyProvenanceSignature(
    { registryId: record.registryId, contentHash: record.contentHash, filename: record.filename, ownerId: record.ownerId, createdAt: record.createdAt },
    record.signature,
  );

  return {
    registered: true as const,
    registryId: record.registryId,
    filename: record.filename,
    title: record.title,
    createdAt: record.createdAt,
    signatureValid,
    owner,
  };
}

export async function listProvenanceForUser(userId: number) {
  return db.select().from(provenanceRecords).where(eq(provenanceRecords.ownerId, userId));
}
