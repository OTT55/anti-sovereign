import { NextResponse } from "next/server";

export function GET() {
  return NextResponse.json({
    name: "FrameVault",
    port: 5504,
    category: "CreativeOS",
    status: "ok",
  });
}
