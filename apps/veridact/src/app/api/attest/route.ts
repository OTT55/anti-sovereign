import { NextResponse } from "next/server";
import { attestCapture } from "@/lib/attestation";
import { attestRequestSchema } from "@/lib/schemas";

const REASON_STATUS: Record<string, number> = {
  device_not_found: 404,
  challenge_not_found: 400,
  challenge_expired: 400,
  challenge_used: 409,
  signature_invalid: 401,
};

export async function POST(req: Request) {
  const parsed = attestRequestSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: "invalid request", issues: parsed.error.issues }, { status: 400 });
  }

  const result = await attestCapture(parsed.data);
  if (!result.ok) {
    return NextResponse.json({ error: result.reason }, { status: REASON_STATUS[result.reason] ?? 400 });
  }
  return NextResponse.json({ manifestId: result.manifestId }, { status: 201 });
}
