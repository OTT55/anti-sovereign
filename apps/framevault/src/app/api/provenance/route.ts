import { NextResponse } from "next/server";
import { DuplicateHashError, registerProvenance } from "@/lib/provenance";
import { provenanceCreateSchema } from "@/lib/schemas";
import { getSessionUserId } from "@/lib/session";

export async function POST(req: Request) {
  const userId = await getSessionUserId();
  if (!userId) return NextResponse.json({ error: "not signed in" }, { status: 401 });

  const parsed = provenanceCreateSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: "invalid request", issues: parsed.error.issues }, { status: 400 });
  }

  try {
    const record = await registerProvenance(userId, parsed.data);
    return NextResponse.json(record, { status: 201 });
  } catch (err) {
    if (err instanceof DuplicateHashError) {
      return NextResponse.json({ error: err.message }, { status: 409 });
    }
    console.error("provenance registration failed", err);
    return NextResponse.json({ error: "registration failed" }, { status: 500 });
  }
}
