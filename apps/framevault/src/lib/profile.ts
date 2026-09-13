import { and, eq, like, or, sql } from "drizzle-orm";
import { db } from "@/db";
import { creatorProfiles, ledgerSpend, profileSkills, provenanceRecords, reputationEvents, reviews, users } from "@/db/schema";
import type { profileUpdateSchema, skillCreateSchema } from "./schemas";
import type { z } from "zod";

export async function getPublicProfile(handle: string) {
  const user = await db.select().from(users).where(eq(users.handle, handle)).get();
  if (!user) return null;

  const [profile, skills, userReviews, reputationTotal, provenance] = await Promise.all([
    db.select().from(creatorProfiles).where(eq(creatorProfiles.userId, user.id)).get(),
    db.select().from(profileSkills).where(eq(profileSkills.userId, user.id)),
    db.select().from(reviews).where(eq(reviews.subjectUserId, user.id)),
    db.select({ total: sql<number>`coalesce(sum(${reputationEvents.weight}), 0)` }).from(reputationEvents).where(eq(reputationEvents.userId, user.id)).get(),
    db.select().from(provenanceRecords).where(eq(provenanceRecords.ownerId, user.id)),
  ]);

  const averageRating = userReviews.length > 0 ? userReviews.reduce((sum, r) => sum + r.rating, 0) / userReviews.length : null;

  return {
    handle: user.handle,
    displayName: user.displayName,
    verified: user.verified,
    createdAt: user.createdAt,
    profile: profile ?? null,
    skills,
    reviews: userReviews,
    averageRating,
    reputation: reputationTotal?.total ?? 0,
    provenance: provenance.map((p) => ({ registryId: p.registryId, title: p.title, filename: p.filename, createdAt: p.createdAt })),
  };
}

export async function updateProfile(userId: number, input: z.infer<typeof profileUpdateSchema>) {
  return db
    .update(creatorProfiles)
    .set({ ...input, updatedAt: new Date().toISOString() })
    .where(eq(creatorProfiles.userId, userId))
    .returning()
    .get();
}

export async function addSkill(userId: number, input: z.infer<typeof skillCreateSchema>) {
  return db.insert(profileSkills).values({ userId, skill: input.skill, level: input.level }).returning().get();
}

export async function removeSkill(userId: number, skillId: number) {
  await db.delete(profileSkills).where(and(eq(profileSkills.id, skillId), eq(profileSkills.userId, userId)));
}

export async function searchCreators(query: string) {
  const pattern = `%${query}%`;
  const rows = await db
    .selectDistinct({ handle: users.handle, displayName: users.displayName })
    .from(users)
    .leftJoin(profileSkills, eq(profileSkills.userId, users.id))
    .where(or(like(users.handle, pattern), like(users.displayName, pattern), like(profileSkills.skill, pattern)))
    .limit(25);
  return rows;
}

export async function getDashboardStats(userId: number) {
  const [reputationTotal, spendTotal, provenanceCount] = await Promise.all([
    db.select({ total: sql<number>`coalesce(sum(${reputationEvents.weight}), 0)` }).from(reputationEvents).where(eq(reputationEvents.userId, userId)).get(),
    db.select({ total: sql<number>`coalesce(sum(${ledgerSpend.amountPence}), 0)` }).from(ledgerSpend).where(eq(ledgerSpend.userId, userId)).get(),
    db.select({ count: sql<number>`count(*)` }).from(provenanceRecords).where(eq(provenanceRecords.ownerId, userId)).get(),
  ]);
  return {
    reputation: reputationTotal?.total ?? 0,
    spendPence: spendTotal?.total ?? 0,
    provenanceCount: provenanceCount?.count ?? 0,
  };
}
