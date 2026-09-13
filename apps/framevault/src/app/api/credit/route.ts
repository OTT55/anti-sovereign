import { NextResponse } from "next/server";
import { creditEvent, UnknownHandleError } from "@/lib/credit";
import { creditRequestSchema } from "@/lib/schemas";
import { isValidServiceKey } from "@/lib/service-auth";

/** The seam every CreativeOS app calls when a real transaction completes — authenticated by a shared service key, not a user session. */
export async function POST(req: Request) {
  if (!isValidServiceKey(req.headers.get("x-service-key"))) {
    return NextResponse.json({ ok: false, error: "invalid service key" }, { status: 401 });
  }

  const parsed = creditRequestSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ ok: false, error: "invalid request", issues: parsed.error.issues }, { status: 400 });
  }

  try {
    const event = await creditEvent(parsed.data);
    return NextResponse.json({ ok: true, eventId: String(event.id) }, { status: 201 });
  } catch (err) {
    if (err instanceof UnknownHandleError) {
      return NextResponse.json({ ok: false, error: err.message }, { status: 404 });
    }
    console.error("credit event failed", err);
    return NextResponse.json({ ok: false, error: "credit event failed" }, { status: 500 });
  }
}
