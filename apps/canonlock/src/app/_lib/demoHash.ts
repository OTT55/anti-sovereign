"use client";

/**
 * Browser-side re-implementation of src/lib/merkle.ts's fold, used only to
 * animate a worked example on the homepage with illustrative sample data.
 * src/lib/merkle.ts uses node:crypto and stays the real, untouched registry
 * logic — this is a separate, honest demo, not a shortcut around it.
 */

async function sha256Hex(bytes: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes.slice().buffer as ArrayBuffer);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export async function textToHashHex(text: string): Promise<string> {
  return sha256Hex(new TextEncoder().encode(text));
}

function hexToBytes(hex: string): Uint8Array {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < bytes.length; i++) {
    bytes[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  }
  return bytes;
}

async function hashPairHex(left: string, right: string): Promise<string> {
  const leftBytes = hexToBytes(left);
  const rightBytes = hexToBytes(right);
  const combined = new Uint8Array(leftBytes.length + rightBytes.length);
  combined.set(leftBytes, 0);
  combined.set(rightBytes, leftBytes.length);
  return sha256Hex(combined);
}

/** Same pairing rule as buildLevels(): an odd node at any level pairs with itself. */
export async function foldLevels(leafHashes: string[]): Promise<string[][]> {
  const levels: string[][] = [leafHashes.slice()];
  let current = leafHashes;
  while (current.length > 1) {
    const next: string[] = [];
    for (let i = 0; i < current.length; i += 2) {
      const left = current[i]!;
      const right = i + 1 < current.length ? current[i + 1]! : left;
      next.push(await hashPairHex(left, right));
    }
    levels.push(next);
    current = next;
  }
  return levels;
}
