import { NextResponse } from "next/server";
import { verifyRush } from "@/lib/rushes";
import { verifyQuerySchema } from "@/lib/schemas";

export async function POST(req: Request) {
  const parsed = verifyQuerySchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success || !parsed.data.hash) {
    return NextResponse.json({ error: "a 'hash' field is required" }, { status: 400 });
  }
  const record = await verifyRush(parsed.data.hash);
  return NextResponse.json(record ? { found: true, rush: record } : { found: false });
}
