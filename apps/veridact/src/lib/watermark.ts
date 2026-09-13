import sharp from "sharp";

const SECRET_BYTES = 7; // 56 bits, matching the legacy product's secret size
const SECRET_BITS = SECRET_BYTES * 8;

function hexToBits(hex: string): number[] {
  const bytes = Buffer.from(hex, "hex");
  const bits: number[] = [];
  for (const byte of bytes) {
    for (let i = 7; i >= 0; i--) bits.push((byte >> i) & 1);
  }
  return bits;
}

function bitsToHex(bits: number[]): string {
  const bytes = Buffer.alloc(SECRET_BYTES);
  for (let byteIndex = 0; byteIndex < SECRET_BYTES; byteIndex++) {
    let value = 0;
    for (let bit = 0; bit < 8; bit++) {
      value = (value << 1) | (bits[byteIndex * 8 + bit] ?? 0);
    }
    bytes[byteIndex] = value;
  }
  return bytes.toString("hex");
}

/**
 * A from-scratch LSB steganographic watermark (the legacy product used
 * Adobe's TrustMark, a deep-learning watermark with no Node/JS port). This
 * embeds each secret bit into the red channel's least-significant bit,
 * repeated across the image and majority-voted on decode for resilience to
 * minor pixel noise. Honesty note: unlike TrustMark, this does NOT survive
 * lossy re-encoding (e.g. re-saving as JPEG) — it only round-trips through
 * lossless operations (PNG re-save, resize, crop-preserving-region). Output
 * is always PNG specifically so the watermark it just embedded round-trips.
 */
export async function embedWatermark(imageBuffer: Buffer, secretHex: string): Promise<Buffer> {
  const bits = hexToBits(secretHex);
  const { data, info } = await sharp(imageBuffer)
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });

  const pixelCount = info.width * info.height;
  const repeats = Math.min(64, Math.floor(pixelCount / SECRET_BITS));
  if (repeats < 3) {
    throw new Error("image too small to embed a watermark reliably");
  }

  const mutable = Buffer.from(data);
  for (let bitIndex = 0; bitIndex < SECRET_BITS; bitIndex++) {
    const bitValue = bits[bitIndex]!;
    for (let rep = 0; rep < repeats; rep++) {
      const pixelIndex = bitIndex + rep * SECRET_BITS;
      const byteOffset = pixelIndex * info.channels; // red channel of this pixel
      mutable[byteOffset] = (mutable[byteOffset]! & 0xfe) | bitValue;
    }
  }

  return sharp(mutable, { raw: { width: info.width, height: info.height, channels: info.channels } })
    .png()
    .toBuffer();
}

/** Best-effort decode — always returns *something*; the caller must confirm the result against a real DB record. */
export async function decodeWatermark(imageBuffer: Buffer): Promise<string | null> {
  try {
    const { data, info } = await sharp(imageBuffer)
      .ensureAlpha()
      .raw()
      .toBuffer({ resolveWithObject: true });

    const pixelCount = info.width * info.height;
    const repeats = Math.min(64, Math.floor(pixelCount / SECRET_BITS));
    if (repeats < 3) return null;

    const bits: number[] = [];
    for (let bitIndex = 0; bitIndex < SECRET_BITS; bitIndex++) {
      let ones = 0;
      for (let rep = 0; rep < repeats; rep++) {
        const pixelIndex = bitIndex + rep * SECRET_BITS;
        const byteOffset = pixelIndex * info.channels;
        if ((data[byteOffset]! & 1) === 1) ones++;
      }
      bits.push(ones * 2 > repeats ? 1 : 0);
    }
    return bitsToHex(bits);
  } catch {
    return null;
  }
}

export function generateWatermarkSecret(): string {
  const bytes = new Uint8Array(SECRET_BYTES);
  crypto.getRandomValues(bytes);
  return Buffer.from(bytes).toString("hex");
}
