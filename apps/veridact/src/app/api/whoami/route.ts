import { NextResponse } from "next/server";

export function GET() {
  return NextResponse.json({
    name: "Veridact",
    port: 5502,
    category: "Attestation",
    status: "ok",
  });
}
