import { NextResponse } from "next/server";
import { AccountExistsError, signup, toIdentity } from "@/lib/identity";
import { signupSchema } from "@/lib/schemas";
import { setSessionCookie } from "@/lib/session";

export async function POST(req: Request) {
  const parsed = signupSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: "invalid request", issues: parsed.error.issues }, { status: 400 });
  }
  try {
    const user = await signup(parsed.data);
    await setSessionCookie(user.id);
    return NextResponse.json({ identity: toIdentity(user) }, { status: 201 });
  } catch (err) {
    if (err instanceof AccountExistsError) {
      return NextResponse.json({ error: err.message }, { status: 409 });
    }
    console.error("signup failed", err);
    return NextResponse.json({ error: "signup failed" }, { status: 500 });
  }
}
