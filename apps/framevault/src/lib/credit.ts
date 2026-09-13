import { eq } from "drizzle-orm";
import { db } from "@/db";
import { ledgerSpend, reputationEvents, reviews, users } from "@/db/schema";
import type { creditRequestSchema } from "./schemas";
import type { z } from "zod";

export class UnknownHandleError extends Error {}

interface RecordEventInput {
  userId: number;
  kind: string;
  weight: number;
  source: string;
  amountPence?: number;
}

export async function recordReputationEvent(input: RecordEventInput) {
  return db
    .insert(reputationEvents)
    .values({ userId: input.userId, kind: input.kind, weight: input.weight, source: input.source, amountPence: input.amountPence ?? null })
    .returning()
    .get();
}

/**
 * The seam every CreativeOS app calls when a real transaction or deliverable
 * completes (a hire paid, an asset licensed, a canon published). Writes the
 * earn-side reputation event and, when a payer is named, the matching
 * spend-side ledger row — giving both sides of the transaction.
 */
export async function creditEvent(input: z.infer<typeof creditRequestSchema>) {
  const recipient = await db.select({ id: users.id }).from(users).where(eq(users.handle, input.handle)).get();
  if (!recipient) throw new UnknownHandleError(`no account with handle "${input.handle}"`);

  const event = await recordReputationEvent({
    userId: recipient.id,
    kind: input.kind,
    weight: input.weight,
    source: input.source,
    amountPence: input.amountPence,
  });

  if (input.review) {
    await db.insert(reviews).values({
      subjectUserId: recipient.id,
      authorName: input.payerHandle ?? input.source,
      authorHandle: input.payerHandle ?? null,
      rating: input.review.rating,
      body: input.review.body,
      context: input.kind,
    });
  }

  if (input.payerHandle && input.amountPence) {
    const payer = await db.select({ id: users.id }).from(users).where(eq(users.handle, input.payerHandle)).get();
    if (payer) {
      await db.insert(ledgerSpend).values({
        userId: payer.id,
        counterparty: input.handle,
        kind: input.kind,
        source: input.source,
        amountPence: input.amountPence,
      });
    }
  }

  return event;
}
