import { NextResponse } from "next/server";
import { DeviceExistsError, enrollDevice } from "@/lib/attestation";
import { enrollRequestSchema } from "@/lib/schemas";

export async function POST(req: Request) {
  const parsed = enrollRequestSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: "invalid request", issues: parsed.error.issues }, { status: 400 });
  }
  try {
    const device = await enrollDevice(parsed.data);
    return NextResponse.json({ handle: device.handle, createdAt: device.createdAt }, { status: 201 });
  } catch (err) {
    if (err instanceof DeviceExistsError) {
      return NextResponse.json({ error: err.message }, { status: 409 });
    }
    console.error("enrollment failed", err);
    return NextResponse.json({ error: "enrollment failed" }, { status: 500 });
  }
}
