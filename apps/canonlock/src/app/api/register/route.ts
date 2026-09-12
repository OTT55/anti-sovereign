import { NextResponse } from "next/server";
import { ZodError } from "zod";
import { DuplicateHashError, registerFile } from "@/lib/registry";
import { registerRequestSchema } from "@/lib/schemas";

export async function POST(req: Request) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "request body must be JSON" }, { status: 400 });
  }

  const parsed = registerRequestSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "invalid request", issues: (parsed.error as ZodError).issues },
      { status: 400 },
    );
  }

  try {
    const certificate = await registerFile(parsed.data);
    return NextResponse.json(certificate, { status: 201 });
  } catch (err) {
    if (err instanceof DuplicateHashError) {
      return NextResponse.json({ error: err.message }, { status: 409 });
    }
    console.error("registration failed", err);
    return NextResponse.json({ error: "registration failed" }, { status: 500 });
  }
}
