import { asc, eq } from "drizzle-orm";
import { db } from "@/db";
import { creators, merkleCheckpoints, registrations } from "@/db/schema";
import { signCertificate, signCheckpoint, verifyCertificateSignature } from "./certificate";
import { getInclusionProof, getMerkleRoot, verifyInclusionProof, type ProofStep } from "./merkle";
import type { RegisterRequest } from "./schemas";
import { requestTimestamp, type TsaResult } from "./tsa";

export class DuplicateHashError extends Error {}

async function allLeafHashesOrdered(): Promise<{ id: number; fileHash: string }[]> {
  return db
    .select({ id: registrations.id, fileHash: registrations.fileHash })
    .from(registrations)
    .orderBy(asc(registrations.leafIndex));
}

export interface RegistryStats {
  count: number;
  merkleRoot: string | null;
}

export async function getStats(): Promise<RegistryStats> {
  const rows = await allLeafHashesOrdered();
  return {
    count: rows.length,
    merkleRoot: rows.length > 0 ? getMerkleRoot(rows.map((r) => r.fileHash)) : null,
  };
}

export interface Certificate {
  registryId: string;
  fileHash: string;
  filename: string;
  description: string | null;
  handle: string;
  createdAt: string;
  leafIndex: number;
  signature: string;
  merkleRoot: string;
  proof: ProofStep[];
  tsa: TsaResult;
}

export async function registerFile(input: RegisterRequest): Promise<Certificate> {
  const existing = await db
    .select({ registryId: registrations.registryId })
    .from(registrations)
    .where(eq(registrations.fileHash, input.fileHash))
    .get();
  if (existing) {
    throw new DuplicateHashError(`this file hash is already registered as ${existing.registryId}`);
  }

  let creator = await db.select().from(creators).where(eq(creators.handle, input.handle)).get();
  if (!creator) {
    creator = await db
      .insert(creators)
      .values({ handle: input.handle, displayName: input.displayName })
      .returning()
      .get();
  }

  const priorRows = await allLeafHashesOrdered();
  const leafIndex = priorRows.length;
  const registryId = `CL-${String(leafIndex + 1).padStart(6, "0")}`;
  const createdAt = new Date().toISOString();
  const description = input.description ?? null;

  const signature = signCertificate({
    registryId,
    fileHash: input.fileHash,
    filename: input.filename,
    description,
    handle: input.handle,
    createdAt,
    leafIndex,
  });

  const tsa = await requestTimestamp(input.fileHash);

  await db.insert(registrations).values({
    registryId,
    creatorId: creator.id,
    filename: input.filename,
    fileHash: input.fileHash,
    description,
    leafIndex,
    signature,
    tsaServer: tsa.server,
    tsaGrantedAt: tsa.status === "granted" ? tsa.grantedAt : null,
    tsaToken: tsa.status === "granted" ? tsa.token : null,
    tsaStatus: tsa.status,
    createdAt,
  });

  const allHashes = [...priorRows.map((r) => r.fileHash), input.fileHash];
  const merkleRoot = getMerkleRoot(allHashes);
  const proof = getInclusionProof(allHashes, leafIndex);

  await db.insert(merkleCheckpoints).values({
    leafCount: allHashes.length,
    merkleRoot,
    signature: signCheckpoint(allHashes.length, merkleRoot),
  });

  return {
    registryId,
    fileHash: input.fileHash,
    filename: input.filename,
    description,
    handle: input.handle,
    createdAt,
    leafIndex,
    signature,
    merkleRoot,
    proof,
    tsa,
  };
}

export type VerifyResult =
  | { registered: false }
  | {
      registered: true;
      registryId: string;
      filename: string;
      description: string | null;
      handle: string;
      createdAt: string;
      leafIndex: number;
      signatureValid: boolean;
      merkleRoot: string;
      proof: ProofStep[];
      inclusionValid: boolean;
      tsa: {
        status: "granted" | "unavailable";
        server: string | null;
        grantedAt: string | null;
        token: string | null;
      };
    };

export async function verifyFile(fileHash: string): Promise<VerifyResult> {
  const record = await db.select().from(registrations).where(eq(registrations.fileHash, fileHash)).get();
  if (!record) {
    return { registered: false };
  }
  const creator = await db.select().from(creators).where(eq(creators.id, record.creatorId)).get();
  if (!creator) {
    throw new Error(`registration ${record.registryId} references a missing creator`);
  }

  const allRows = await allLeafHashesOrdered();
  const allHashes = allRows.map((r) => r.fileHash);
  const merkleRoot = getMerkleRoot(allHashes);
  const proof = getInclusionProof(allHashes, record.leafIndex);
  const inclusionValid = verifyInclusionProof(record.fileHash, proof, merkleRoot);

  const signatureValid = verifyCertificateSignature(
    {
      registryId: record.registryId,
      fileHash: record.fileHash,
      filename: record.filename,
      description: record.description,
      handle: creator.handle,
      createdAt: record.createdAt,
      leafIndex: record.leafIndex,
    },
    record.signature,
  );

  return {
    registered: true,
    registryId: record.registryId,
    filename: record.filename,
    description: record.description,
    handle: creator.handle,
    createdAt: record.createdAt,
    leafIndex: record.leafIndex,
    signatureValid,
    merkleRoot,
    proof,
    inclusionValid,
    tsa: {
      status: record.tsaStatus,
      server: record.tsaServer,
      grantedAt: record.tsaGrantedAt,
      token: record.tsaToken,
    },
  };
}
