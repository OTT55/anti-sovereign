import { describe, expect, it } from "vitest";
import { buildLevels, getInclusionProof, getMerkleRoot, sha256Hex, verifyInclusionProof } from "./merkle";

describe("merkle tree", () => {
  const leaves = ["a", "b", "c", "d", "e"].map((s) => sha256Hex(s));

  it("produces a stable root for a fixed leaf set", () => {
    expect(getMerkleRoot(leaves)).toBe(getMerkleRoot(leaves));
  });

  it("duplicates the odd node out at each level instead of dropping it", () => {
    const levels = buildLevels(leaves);
    expect(levels[0]).toHaveLength(5);
    expect(levels[1]).toHaveLength(3); // pairs: (0,1) (2,3) (4,4)
    expect(levels[2]).toHaveLength(2); // pairs: (0,1) (2,2)
    expect(levels[3]).toHaveLength(1);
  });

  it("generates a proof that verifies against the true root for every leaf", () => {
    const root = getMerkleRoot(leaves);
    for (let i = 0; i < leaves.length; i++) {
      const proof = getInclusionProof(leaves, i);
      expect(verifyInclusionProof(leaves[i]!, proof, root)).toBe(true);
    }
  });

  it("rejects a proof for the wrong leaf hash", () => {
    const root = getMerkleRoot(leaves);
    const proof = getInclusionProof(leaves, 0);
    expect(verifyInclusionProof(sha256Hex("tampered"), proof, root)).toBe(false);
  });

  it("rejects a valid proof folded against the wrong root", () => {
    const proof = getInclusionProof(leaves, 2);
    expect(verifyInclusionProof(leaves[2]!, proof, sha256Hex("wrong-root"))).toBe(false);
  });

  it("handles a single-leaf tree (root equals the leaf)", () => {
    const single = [sha256Hex("only")];
    expect(getMerkleRoot(single)).toBe(single[0]);
    expect(getInclusionProof(single, 0)).toEqual([]);
  });

  it("throws on an out-of-range leaf index", () => {
    expect(() => getInclusionProof(leaves, 99)).toThrow();
  });
});
