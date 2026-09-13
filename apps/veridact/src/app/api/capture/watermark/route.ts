import { NextResponse } from "next/server";
import { embedWatermark, generateWatermarkSecret } from "@/lib/watermark";

export async function POST(req: Request) {
  const form = await req.formData().catch(() => null);
  const file = form?.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json({ error: "multipart field 'file' is required" }, { status: 400 });
  }

  const secret = generateWatermarkSecret();
  const buffer = Buffer.from(await file.arrayBuffer());

  try {
    const watermarked = await embedWatermark(buffer, secret);
    return new NextResponse(new Uint8Array(watermarked), {
      status: 200,
      headers: {
        "content-type": "image/png",
        "x-watermark-secret": secret,
      },
    });
  } catch (err) {
    console.error("watermark embedding failed", err);
    return NextResponse.json({ error: "could not embed a watermark in this image" }, { status: 422 });
  }
}
