import { createHash } from "node:crypto";

export function sha256Hex(data: Buffer | string): string {
  return createHash("sha256").update(data).digest("hex");
}

function hashPair(left: string, right: string): string {
  return createHash("sha256")
    .update(Buffer.from(left, "hex"))
    .update(Buffer.from(right, "hex"))
    .digest("hex");
}

export interface ProofStep {
  siblingHash: string;
  /** Which side the SIBLING sits on, relative to the node being folded up. */
  position: "left" | "right";
}

/**
 * Every level of the tree, leaves first and the root last as a single-element
 * array. An odd node at any level is paired with itself, matching the
 * original product's tree construction.
 */
export function buildLevels(leafHashes: string[]): string[][] {
  if (leafHashes.length === 0) {
    throw new Error("cannot build a Merkle tree with zero leaves");
  }
  const levels: string[][] = [leafHashes.slice()];
  let current = leafHashes;
  while (current.length > 1) {
    const next: string[] = [];
    for (let i = 0; i < current.length; i += 2) {
      const left = current[i]!;
      const right = i + 1 < current.length ? current[i + 1]! : left;
      next.push(hashPair(left, right));
    }
    levels.push(next);
    current = next;
  }
  return levels;
}

export function getMerkleRoot(leafHashes: string[]): string {
  const levels = buildLevels(leafHashes);
  return levels[levels.length - 1]![0]!;
}

/** Ordered sibling-hash chain from a leaf up to (but not including) the root. */
export function getInclusionProof(leafHashes: string[], leafIndex: number): ProofStep[] {
  if (leafIndex < 0 || leafIndex >= leafHashes.length) {
    throw new Error("leaf index out of range");
  }
  const levels = buildLevels(leafHashes);
  const proof: ProofStep[] = [];
  let index = leafIndex;
  for (let level = 0; level < levels.length - 1; level++) {
    const nodes = levels[level]!;
    const isRightNode = index % 2 === 1;
    const siblingIndex = isRightNode ? index - 1 : index + 1;
    const sibling = siblingIndex < nodes.length ? nodes[siblingIndex]! : nodes[index]!;
    proof.push({ siblingHash: sibling, position: isRightNode ? "left" : "right" });
    index = Math.floor(index / 2);
  }
  return proof;
}

/** Recomputes the root by folding a leaf hash through its proof, and compares. */
export function verifyInclusionProof(leafHash: string, proof: ProofStep[], root: string): boolean {
  let computed = leafHash;
  for (const step of proof) {
    computed =
      step.position === "left" ? hashPair(step.siblingHash, computed) : hashPair(computed, step.siblingHash);
  }
  return computed === root;
}
