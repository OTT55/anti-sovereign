import { NextResponse } from "next/server";
import { verifyFile } from "@/lib/registry";
import { verifyQuerySchema } from "@/lib/schemas";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const parsed = verifyQuerySchema.safeParse({ hash: searchParams.get("hash") });
  if (!parsed.success) {
    return NextResponse.json(
      { error: "invalid request", issues: parsed.error.issues },
      { status: 400 },
    );
  }

  const result = await verifyFile(parsed.data.hash);
  return NextResponse.json(result);
}
