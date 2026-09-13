import { NextResponse } from "next/server";
import { getDashboardStats } from "@/lib/profile";
import { getSessionUserId } from "@/lib/session";

export async function GET() {
  const userId = await getSessionUserId();
  if (!userId) return NextResponse.json({ error: "not signed in" }, { status: 401 });
  return NextResponse.json(await getDashboardStats(userId));
}
