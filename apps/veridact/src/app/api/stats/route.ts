import { NextResponse } from "next/server";
import { getStats } from "@/lib/attestation";

export async function GET() {
  return NextResponse.json(await getStats());
}
