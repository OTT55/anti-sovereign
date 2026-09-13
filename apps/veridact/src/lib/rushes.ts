import { randomBytes } from "node:crypto";
import { desc, eq } from "drizzle-orm";
import { db } from "@/db";
import { filmRushes } from "@/db/schema";
import type { rushRegisterSchema } from "./schemas";
import type { z } from "zod";

async function generateUniqueRushId(): Promise<string> {
  for (let attempt = 0; attempt < 10; attempt++) {
    const candidate = `RUSH-${randomBytes(4).toString("hex").toUpperCase()}`;
    const existing = await db.select({ id: filmRushes.id }).from(filmRushes).where(eq(filmRushes.rushId, candidate)).get();
    if (!existing) return candidate;
  }
  throw new Error("failed to allocate a unique rush id");
}

export class DuplicateRushHashError extends Error {}

export async function registerRush(input: z.infer<typeof rushRegisterSchema>) {
  const existing = await db.select({ rushId: filmRushes.rushId }).from(filmRushes).where(eq(filmRushes.mediaHash, input.mediaHash)).get();
  if (existing) {
    throw new DuplicateRushHashError(`this file hash is already logged as ${existing.rushId}`);
  }
  const rushId = await generateUniqueRushId();
  return db
    .insert(filmRushes)
    .values({
      rushId,
      production: input.production,
      rollNumber: input.rollNumber ?? null,
      sceneTake: input.sceneTake ?? null,
      fileName: input.fileName,
      mediaHash: input.mediaHash,
      framerate: input.framerate ?? null,
      ditNotes: input.ditNotes ?? null,
      capturedAt: input.capturedAt,
    })
    .returning()
    .get();
}

export async function listRushes(limit = 100) {
  return db.select().from(filmRushes).orderBy(desc(filmRushes.createdAt)).limit(limit);
}

export async function verifyRush(mediaHash: string) {
  const record = await db.select().from(filmRushes).where(eq(filmRushes.mediaHash, mediaHash)).get();
  return record ?? null;
}
