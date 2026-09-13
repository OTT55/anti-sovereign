import { NextResponse } from "next/server";
import { issueChallenge } from "@/lib/challenge";

export async function POST() {
  const challenge = await issueChallenge();
  return NextResponse.json(challenge);
}
