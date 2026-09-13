import { NextResponse } from "next/server";
import { authenticate, InvalidCredentialsError, toIdentity } from "@/lib/identity";
import { loginSchema } from "@/lib/schemas";
import { setSessionCookie } from "@/lib/session";

export async function POST(req: Request) {
  const parsed = loginSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: "invalid request" }, { status: 400 });
  }
  try {
    const user = await authenticate(parsed.data.handle, parsed.data.password);
    await setSessionCookie(user.id);
    return NextResponse.json({ identity: toIdentity(user) });
  } catch (err) {
    if (err instanceof InvalidCredentialsError) {
      return NextResponse.json({ error: "invalid handle or password" }, { status: 401 });
    }
    console.error("login failed", err);
    return NextResponse.json({ error: "login failed" }, { status: 500 });
  }
}
