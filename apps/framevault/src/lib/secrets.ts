import { randomBytes } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

const SECRETS_PATH = path.join(process.cwd(), ".framevault_secrets");

interface Secrets {
  /** Signs provenance certificates, mirroring every other product's per-app HMAC key. */
  signingKey: string;
  /** Signs session cookies. */
  sessionKey: string;
  /** Shared secret other CreativeOS apps present via X-Service-Key to call /api/credit. */
  serviceKey: string;
}

let cached: Secrets | null = null;

function loadOrCreate(): Secrets {
  if (cached) return cached;

  if (process.env.FRAMEVAULT_SERVICE_KEY && process.env.FRAMEVAULT_SIGNING_KEY && process.env.FRAMEVAULT_SESSION_KEY) {
    cached = {
      signingKey: process.env.FRAMEVAULT_SIGNING_KEY,
      sessionKey: process.env.FRAMEVAULT_SESSION_KEY,
      serviceKey: process.env.FRAMEVAULT_SERVICE_KEY,
    };
    return cached;
  }

  if (existsSync(SECRETS_PATH)) {
    cached = JSON.parse(readFileSync(SECRETS_PATH, "utf8")) as Secrets;
    return cached;
  }

  cached = {
    signingKey: randomBytes(32).toString("hex"),
    sessionKey: randomBytes(32).toString("hex"),
    serviceKey: randomBytes(24).toString("hex"),
  };
  writeFileSync(SECRETS_PATH, JSON.stringify(cached, null, 2), { mode: 0o600 });
  return cached;
}

export function getSigningKey(): Buffer {
  return Buffer.from(loadOrCreate().signingKey, "hex");
}

export function getSessionKey(): Buffer {
  return Buffer.from(loadOrCreate().sessionKey, "hex");
}

export function getServiceKey(): string {
  return loadOrCreate().serviceKey;
}
