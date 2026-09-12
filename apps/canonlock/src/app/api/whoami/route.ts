import { NextResponse } from "next/server";

export function GET() {
  return NextResponse.json({
    name: "Canonlock",
    port: 5501,
    category: "Registry",
    status: "ok",
  });
}
