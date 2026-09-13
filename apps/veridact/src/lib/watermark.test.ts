import sharp from "sharp";
import { describe, expect, it } from "vitest";
import { decodeWatermark, embedWatermark, generateWatermarkSecret } from "./watermark";

async function makeTestImage(width = 128, height = 128): Promise<Buffer> {
  return sharp({
    create: { width, height, channels: 3, background: { r: 60, g: 120, b: 200 } },
  })
    .png()
    .toBuffer();
}

describe("watermark", () => {
  it("decodes the exact secret that was embedded", async () => {
    const image = await makeTestImage();
    const secret = generateWatermarkSecret();
    const watermarked = await embedWatermark(image, secret);
    const decoded = await decodeWatermark(watermarked);
    expect(decoded).toBe(secret);
  });

  it("survives a lossless PNG round-trip (re-decode, re-encode)", async () => {
    const image = await makeTestImage();
    const secret = generateWatermarkSecret();
    const watermarked = await embedWatermark(image, secret);

    // Simulate the file being re-saved as PNG by another tool.
    const roundTripped = await sharp(watermarked).png().toBuffer();
    const decoded = await decodeWatermark(roundTripped);
    expect(decoded).toBe(secret);
  });

  it("produces different watermarked bytes for different secrets", async () => {
    const image = await makeTestImage();
    const a = await embedWatermark(image, generateWatermarkSecret());
    const b = await embedWatermark(image, generateWatermarkSecret());
    expect(Buffer.compare(a, b)).not.toBe(0);
  });

  it("refuses to embed into an image too small for reliable redundancy", async () => {
    const tiny = await makeTestImage(4, 4);
    await expect(embedWatermark(tiny, generateWatermarkSecret())).rejects.toThrow();
  });

  it("decode returns null (not a crash) for a non-image buffer", async () => {
    const decoded = await decodeWatermark(Buffer.from("not an image"));
    expect(decoded).toBeNull();
  });
});
