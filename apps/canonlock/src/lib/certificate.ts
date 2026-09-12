import { createHmac, timingSafeEqual } from "node:crypto";
import { getSigningKey } from "./signing-key";

export interface CertificateFields {
  registryId: string;
  fileHash: string;
  filename: string;
  description: string | null;
  handle: string;
  createdAt: string;
  leafIndex: number;
}

function canonicalMessage(fields: CertificateFields): string {
  return [
    fields.registryId,
    fields.fileHash,
    fields.filename,
    fields.description ?? "",
    fields.handle,
    fields.createdAt,
    String(fields.leafIndex),
  ].join("|");
}

/** HMAC-SHA256 "wax seal" over every certificate field — tampering with any of them breaks it. */
export function signCertificate(fields: CertificateFields): string {
  return createHmac("sha256", getSigningKey()).update(canonicalMessage(fields)).digest("hex");
}

export function verifyCertificateSignature(fields: CertificateFields, signature: string): boolean {
  const expected = signCertificate(fields);
  const expectedBuf = Buffer.from(expected, "hex");
  const actualBuf = Buffer.from(signature, "hex");
  if (expectedBuf.length !== actualBuf.length) return false;
  return timingSafeEqual(expectedBuf, actualBuf);
}

/** HMAC over a periodic snapshot of the whole tree's size + root. */
export function signCheckpoint(leafCount: number, merkleRoot: string): string {
  return createHmac("sha256", getSigningKey()).update(`${leafCount}|${merkleRoot}`).digest("hex");
}
