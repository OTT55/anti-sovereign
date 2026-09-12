import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { existsSync, rmSync } from "node:fs";
import path from "node:path";

const secretPath = path.join(process.cwd(), ".canonlock_secret");

describe("certificate signing", () => {
  beforeEach(() => {
    if (existsSync(secretPath)) rmSync(secretPath);
  });
  afterEach(() => {
    if (existsSync(secretPath)) rmSync(secretPath);
  });

  it("verifies a signature it just produced", async () => {
    const { signCertificate, verifyCertificateSignature } = await import("./certificate");
    const fields = {
      registryId: "CL-000001",
      fileHash: "a".repeat(64),
      filename: "test.txt",
      description: null,
      handle: "alice",
      createdAt: "2026-01-01T00:00:00.000Z",
      leafIndex: 0,
    };
    const signature = signCertificate(fields);
    expect(verifyCertificateSignature(fields, signature)).toBe(true);
  });

  it("rejects a signature when any field is tampered with", async () => {
    const { signCertificate, verifyCertificateSignature } = await import("./certificate");
    const fields = {
      registryId: "CL-000001",
      fileHash: "a".repeat(64),
      filename: "test.txt",
      description: null,
      handle: "alice",
      createdAt: "2026-01-01T00:00:00.000Z",
      leafIndex: 0,
    };
    const signature = signCertificate(fields);
    expect(verifyCertificateSignature({ ...fields, filename: "renamed.txt" }, signature)).toBe(false);
  });
});
