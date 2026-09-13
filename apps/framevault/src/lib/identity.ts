import { eq, or } from "drizzle-orm";
import { db } from "@/db";
import { creatorProfiles, users } from "@/db/schema";
import { hashPassword, verifyPassword } from "./password";
import type { signupSchema } from "./schemas";
import type { z } from "zod";

export class AccountExistsError extends Error {}
export class InvalidCredentialsError extends Error {}

export async function signup(input: z.infer<typeof signupSchema>) {
  const existing = await db
    .select({ id: users.id })
    .from(users)
    .where(or(eq(users.email, input.email), eq(users.handle, input.handle)))
    .get();
  if (existing) {
    throw new AccountExistsError("that email or handle is already registered");
  }

  const passwordHash = await hashPassword(input.password);
  const user = await db
    .insert(users)
    .values({ email: input.email, handle: input.handle, displayName: input.displayName, passwordHash })
    .returning()
    .get();
  await db.insert(creatorProfiles).values({ userId: user.id });
  return user;
}

export async function authenticate(handle: string, password: string) {
  const user = await db.select().from(users).where(eq(users.handle, handle)).get();
  if (!user) throw new InvalidCredentialsError("no account with that handle");
  const valid = await verifyPassword(password, user.passwordHash);
  if (!valid) throw new InvalidCredentialsError("incorrect password");
  return user;
}

export function toIdentity(user: { handle: string; displayName: string; verified: boolean }) {
  return { handle: user.handle, displayName: user.displayName, verified: user.verified };
}
