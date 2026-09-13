import { NextResponse } from "next/server";
import { addSkill } from "@/lib/profile";
import { skillCreateSchema } from "@/lib/schemas";
import { getSessionUserId } from "@/lib/session";

export async function POST(req: Request) {
  const userId = await getSessionUserId();
  if (!userId) return NextResponse.json({ error: "not signed in" }, { status: 401 });

  const parsed = skillCreateSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: "invalid request", issues: parsed.error.issues }, { status: 400 });
  }

  const skill = await addSkill(userId, parsed.data);
  return NextResponse.json(skill, { status: 201 });
}
