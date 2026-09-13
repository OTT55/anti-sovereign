import { NextResponse } from "next/server";
import { sha256HexOfBuffer, verifyMedia } from "@/lib/attestation";

export async function POST(req: Request) {
  const form = await req.formData().catch(() => null);
  const file = form?.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json({ error: "multipart field 'file' is required" }, { status: 400 });
  }
  const manifestId = form?.get("manifestId");

  const buffer = Buffer.from(await file.arrayBuffer());
  const fileHash = sha256HexOfBuffer(buffer);

  const result = await verifyMedia(fileHash, buffer, typeof manifestId === "string" && manifestId ? manifestId : undefined);
  return NextResponse.json({ fileHash, ...result });
}
