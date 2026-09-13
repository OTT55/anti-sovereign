import { NextResponse } from "next/server";
import { profileUpdateSchema } from "@/lib/schemas";
import { updateProfile } from "@/lib/profile";
import { getSessionUserId } from "@/lib/session";

export async function POST(req: Request) {
  const userId = await getSessionUserId();
  if (!userId) return NextResponse.json({ error: "not signed in" }, { status: 401 });

  const parsed = profileUpdateSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: "invalid request", issues: parsed.error.issues }, { status: 400 });
  }

  const profile = await updateProfile(userId, parsed.data);
  return NextResponse.json(profile);
}
