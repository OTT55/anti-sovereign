import { NextResponse } from "next/server";
import { searchCreators } from "@/lib/profile";

export async function GET(req: Request) {
  const q = new URL(req.url).searchParams.get("q")?.trim();
  if (!q) return NextResponse.json([]);
  return NextResponse.json(await searchCreators(q));
}
