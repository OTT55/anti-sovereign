import { NextResponse } from "next/server";
import { checkAllApps } from "@/lib/health";

export const dynamic = "force-dynamic";

export async function GET() {
  const health = await checkAllApps();
  return NextResponse.json(health);
}
