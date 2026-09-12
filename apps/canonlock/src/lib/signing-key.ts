import { randomBytes } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

const SECRET_PATH = path.join(process.cwd(), ".canonlock_secret");

/**
 * A per-install HMAC signing key, generated once and persisted next to the
 * app (gitignored) — mirrors every other product's `.{app}_secret` pattern
 * in this portfolio. Never committed, never logged.
 */
export function getSigningKey(): Buffer {
  if (process.env.CANONLOCK_SIGNING_KEY) {
    return Buffer.from(process.env.CANONLOCK_SIGNING_KEY, "hex");
  }
  if (existsSync(SECRET_PATH)) {
    return Buffer.from(readFileSync(SECRET_PATH, "utf8").trim(), "hex");
  }
  const key = randomBytes(32);
  writeFileSync(SECRET_PATH, key.toString("hex"), { mode: 0o600 });
  return key;
}
