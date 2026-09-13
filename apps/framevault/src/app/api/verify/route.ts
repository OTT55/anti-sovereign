import { NextResponse } from "next/server";
import { verifyProvenanceByHash } from "@/lib/provenance";
import { verifyRequestSchema } from "@/lib/schemas";

export async function POST(req: Request) {
  const parsed = verifyRequestSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: "a valid sha256 'hash' is required" }, { status: 400 });
  }
  return NextResponse.json(await verifyProvenanceByHash(parsed.data.hash));
}
