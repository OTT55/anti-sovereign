import { eq } from "drizzle-orm";
import { NextResponse } from "next/server";
import { db } from "@/db";
import { users } from "@/db/schema";
import { toIdentity } from "@/lib/identity";
import { getSessionUserId } from "@/lib/session";

export async function GET() {
  const userId = await getSessionUserId();
  if (!userId) return NextResponse.json({ identity: null });
  const user = await db.select().from(users).where(eq(users.id, userId)).get();
  return NextResponse.json({ identity: user ? toIdentity(user) : null });
}
