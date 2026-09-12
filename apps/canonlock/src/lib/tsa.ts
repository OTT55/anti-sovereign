import { randomBytes } from "node:crypto";
import * as asn1js from "asn1js";

const TSA_URL = process.env.CANONLOCK_TSA_URL ?? "https://freetsa.org/tsr";
const SHA256_OID = "2.16.840.1.101.3.4.2.1";
const REQUEST_TIMEOUT_MS = 8000;

export type TsaResult =
  | { status: "granted"; server: string; grantedAt: string | null; token: string }
  | { status: "unavailable"; server: string; reason: string };

function toArrayBuffer(buf: Buffer): ArrayBuffer {
  return buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) as ArrayBuffer;
}

/** Builds a real RFC 3161 TimeStampReq (DER) for a SHA-256 message imprint. */
function buildTimeStampReq(hashHex: string): ArrayBuffer {
  const hashBytes = Buffer.from(hashHex, "hex");
  const nonce = randomBytes(8);
  nonce[0] = nonce[0]! & 0x7f; // keep the DER INTEGER unambiguously positive

  const messageImprint = new asn1js.Sequence({
    value: [
      new asn1js.Sequence({
        value: [new asn1js.ObjectIdentifier({ value: SHA256_OID }), new asn1js.Null()],
      }),
      new asn1js.OctetString({ valueHex: toArrayBuffer(hashBytes) }),
    ],
  });

  const req = new asn1js.Sequence({
    value: [
      new asn1js.Integer({ value: 1 }), // version
      messageImprint,
      new asn1js.Integer({ valueHex: toArrayBuffer(nonce) }), // nonce
      new asn1js.Boolean({ value: true }), // certReq: ask the TSA to include its cert
    ],
  });

  return req.toBER(false);
}

/** Best-effort depth-first search for the TSTInfo's genTime inside the response. */
function findGeneralizedTime(node: unknown): Date | null {
  if (node instanceof asn1js.GeneralizedTime) {
    try {
      return node.toDate();
    } catch {
      return null;
    }
  }
  if (
    node &&
    typeof node === "object" &&
    "valueBlock" in node &&
    node.valueBlock &&
    typeof node.valueBlock === "object" &&
    "value" in node.valueBlock &&
    Array.isArray(node.valueBlock.value)
  ) {
    for (const child of node.valueBlock.value) {
      const found = findGeneralizedTime(child);
      if (found) return found;
    }
  }
  return null;
}

/**
 * Requests a real RFC 3161 timestamp for a SHA-256 hash from a public TSA.
 * If the TSA is unreachable, rejects the request, or returns something we
 * can't parse, this returns an honest "unavailable" result rather than
 * fabricating a token that would look real but prove nothing.
 */
export async function requestTimestamp(fileHashHex: string): Promise<TsaResult> {
  try {
    const reqDer = buildTimeStampReq(fileHashHex);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    let res: Response;
    try {
      res = await fetch(TSA_URL, {
        method: "POST",
        headers: {
          "content-type": "application/timestamp-query",
          accept: "application/timestamp-reply",
        },
        body: reqDer,
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timeout);
    }

    if (!res.ok) {
      return { status: "unavailable", server: TSA_URL, reason: `HTTP ${res.status}` };
    }

    const respBytes = new Uint8Array(await res.arrayBuffer());
    const parsed = asn1js.fromBER(respBytes.buffer);
    if (parsed.offset === -1) {
      return { status: "unavailable", server: TSA_URL, reason: "malformed TSA response" };
    }

    const root = parsed.result;
    if (!(root instanceof asn1js.Sequence) || root.valueBlock.value.length < 1) {
      return { status: "unavailable", server: TSA_URL, reason: "unexpected response shape" };
    }

    const pkiStatusInfo = root.valueBlock.value[0];
    if (!(pkiStatusInfo instanceof asn1js.Sequence) || pkiStatusInfo.valueBlock.value.length < 1) {
      return { status: "unavailable", server: TSA_URL, reason: "missing PKIStatusInfo" };
    }
    const statusNode = pkiStatusInfo.valueBlock.value[0];
    const status = statusNode instanceof asn1js.Integer ? statusNode.valueBlock.valueDec : -1;

    // PKIStatus: 0 = granted, 1 = grantedWithMods; anything else is a rejection.
    if (status !== 0 && status !== 1) {
      return { status: "unavailable", server: TSA_URL, reason: `TSA rejected the request (status ${status})` };
    }

    const timeStampToken = root.valueBlock.value[1];
    if (!timeStampToken) {
      return { status: "unavailable", server: TSA_URL, reason: "TSA granted but returned no token" };
    }

    const tokenDer = timeStampToken.toBER(false);
    const grantedAt = findGeneralizedTime(timeStampToken);

    return {
      status: "granted",
      server: TSA_URL,
      grantedAt: grantedAt ? grantedAt.toISOString() : null,
      token: Buffer.from(tokenDer).toString("base64"),
    };
  } catch (err) {
    const reason = err instanceof Error ? err.message : "unknown error";
    return { status: "unavailable", server: TSA_URL, reason };
  }
}
