import { NextResponse } from "next/server";
import { authenticate, InvalidCredentialsError, toIdentity } from "@/lib/identity";
import { authenticateRequestSchema } from "@/lib/schemas";

/**
 * Called by every other CreativeOS app's login form — the handle+password is
 * forwarded once and never stored by the caller. FrameVault is the single
 * source of truth for identity across the whole suite.
 */
export async function POST(req: Request) {
  const parsed = authenticateRequestSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ ok: false, error: "invalid request" }, { status: 400 });
  }
  try {
    const user = await authenticate(parsed.data.handle, parsed.data.password);
    return NextResponse.json({ ok: true, identity: toIdentity(user) });
  } catch (err) {
    if (err instanceof InvalidCredentialsError) {
      return NextResponse.json({ ok: false, error: "invalid handle or password" }, { status: 401 });
    }
    console.error("service authenticate failed", err);
    return NextResponse.json({ ok: false, error: "authentication failed" }, { status: 500 });
  }
}
