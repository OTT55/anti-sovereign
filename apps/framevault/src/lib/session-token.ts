import { createHmac, timingSafeEqual } from "node:crypto";
import { getSessionKey } from "./secrets";

const SESSION_TTL_MS = 30 * 24 * 60 * 60 * 1000;

interface SessionPayload {
  userId: number;
  exp: number;
}

function sign(payload: string): string {
  return createHmac("sha256", getSessionKey()).update(payload).digest("hex");
}

export function createSessionToken(userId: number): string {
  const payload: SessionPayload = { userId, exp: Date.now() + SESSION_TTL_MS };
  const encoded = Buffer.from(JSON.stringify(payload)).toString("base64url");
  return `${encoded}.${sign(encoded)}`;
}

export function verifySessionToken(token: string): number | null {
  const [encoded, signature] = token.split(".");
  if (!encoded || !signature) return null;

  const expected = sign(encoded);
  const expectedBuf = Buffer.from(expected, "hex");
  const actualBuf = Buffer.from(signature, "hex");
  if (expectedBuf.length !== actualBuf.length || !timingSafeEqual(expectedBuf, actualBuf)) return null;

  try {
    const payload = JSON.parse(Buffer.from(encoded, "base64url").toString("utf8")) as SessionPayload;
    if (payload.exp < Date.now()) return null;
    return payload.userId;
  } catch {
    return null;
  }
}

export const SESSION_COOKIE_NAME = "fv_session";
export const SESSION_TTL_SECONDS = SESSION_TTL_MS / 1000;
