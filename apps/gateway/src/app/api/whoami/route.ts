import { NextResponse } from "next/server";

export function GET() {
  return NextResponse.json({
    name: "Gateway",
    port: 5500,
    category: "Infra",
    status: "ok",
  });
}
