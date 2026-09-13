import { NextResponse } from "next/server";
import { removeSkill } from "@/lib/profile";
import { getSessionUserId } from "@/lib/session";

export async function DELETE(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const userId = await getSessionUserId();
  if (!userId) return NextResponse.json({ error: "not signed in" }, { status: 401 });

  const { id } = await params;
  await removeSkill(userId, Number(id));
  return NextResponse.json({ ok: true });
}
