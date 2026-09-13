import { NextResponse } from "next/server";
import { DuplicateRushHashError, registerRush } from "@/lib/rushes";
import { rushRegisterSchema } from "@/lib/schemas";

export async function POST(req: Request) {
  const parsed = rushRegisterSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: "invalid request", issues: parsed.error.issues }, { status: 400 });
  }
  try {
    const rush = await registerRush(parsed.data);
    return NextResponse.json(rush, { status: 201 });
  } catch (err) {
    if (err instanceof DuplicateRushHashError) {
      return NextResponse.json({ error: err.message }, { status: 409 });
    }
    console.error("rush registration failed", err);
    return NextResponse.json({ error: "rush registration failed" }, { status: 500 });
  }
}
