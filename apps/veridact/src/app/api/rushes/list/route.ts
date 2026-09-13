import { NextResponse } from "next/server";
import { listRushes } from "@/lib/rushes";

export async function GET() {
  return NextResponse.json(await listRushes());
}
