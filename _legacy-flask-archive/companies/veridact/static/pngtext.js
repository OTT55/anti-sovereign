// Embed/read a PNG tEXt metadata chunk — used to carry Veridact's proof code
// (the manifest ID) inside the saved photo itself, so there's one file to
// keep track of instead of a photo plus a separate code to copy (decisions/0008).
//
// This is plain, 30-year-old PNG spec (a tEXt chunk: keyword + NUL + text,
// wrapped in the standard length/type/CRC32 chunk framing) — not a novel
// format, and not the robust/recompression-surviving watermark described as
// later, separate work: any recompression or format conversion (e.g. sending
// the photo through an app that re-encodes it) strips this metadata just
// like it strips C2PA or EXIF. It's a convenience for the direct-file case,
// not a durability claim.

const VD_PNG_SIG = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];

// Standard PNG/zlib CRC-32 (polynomial 0xEDB88320), computed once.
const VD_CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
    table[n] = c >>> 0;
  }
  return table;
})();

function vdCrc32(bytes) {
  let crc = 0xffffffff;
  for (let i = 0; i < bytes.length; i++) {
    crc = VD_CRC_TABLE[(crc ^ bytes[i]) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function vdU32(n) {
  return [(n >>> 24) & 0xff, (n >>> 16) & 0xff, (n >>> 8) & 0xff, n & 0xff];
}

function vdIsPng(bytes) {
  return VD_PNG_SIG.every((b, i) => bytes[i] === b);
}

// Insert a tEXt chunk (keyword/text ASCII only — true for our manifest IDs)
// right after the mandatory IHDR chunk, which is always the first chunk.
async function vdEmbedPngText(blob, keyword, text) {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  if (!vdIsPng(bytes)) return blob; // not a PNG (shouldn't happen for our own captures) — leave untouched

  const ihdrLength = new DataView(bytes.buffer, 8, 4).getUint32(0);
  const ihdrEnd = 8 + 4 + 4 + ihdrLength + 4; // sig + [len+type+data+crc]

  const kw = new TextEncoder().encode(keyword);
  const txt = new TextEncoder().encode(text);
  const data = new Uint8Array(kw.length + 1 + txt.length);
  data.set(kw, 0);
  data[kw.length] = 0;
  data.set(txt, kw.length + 1);

  const type = new TextEncoder().encode("tEXt");
  const crcInput = new Uint8Array(type.length + data.length);
  crcInput.set(type, 0);
  crcInput.set(data, type.length);
  const crc = vdCrc32(crcInput);

  const chunk = new Uint8Array([
    ...vdU32(data.length),
    ...type,
    ...data,
    ...vdU32(crc),
  ]);

  const out = new Uint8Array(bytes.length + chunk.length);
  out.set(bytes.subarray(0, ihdrEnd), 0);
  out.set(chunk, ihdrEnd);
  out.set(bytes.subarray(ihdrEnd), ihdrEnd + chunk.length);
  return new Blob([out], { type: "image/png" });
}

// Remove a tEXt chunk we previously inserted (by keyword), recovering the
// EXACT original bytes byte-for-byte — this is a plain removal of the exact
// chunk vdEmbedPngText added, not a re-encode, so it's lossless. This matters
// for verification: embedding the proof code changes the file's hash, so a
// saved photo would otherwise never match the hash that was actually signed.
// Stripping the chunk back out before hashing is what lets "verify the photo
// Veridact just gave you" still resolve to VERIFIED CAPTURE rather than
// ALTERED against itself (decisions/0008).
async function vdStripPngText(fileOrBlob, keyword) {
  const bytes = new Uint8Array(await fileOrBlob.arrayBuffer());
  if (!vdIsPng(bytes)) return { bytes, stripped: false };

  let offset = 8;
  while (offset + 8 <= bytes.length) {
    const length = new DataView(bytes.buffer, offset, 4).getUint32(0);
    const type = String.fromCharCode(...bytes.subarray(offset + 4, offset + 8));
    const dataStart = offset + 8;
    const dataEnd = dataStart + length;
    const chunkEnd = dataEnd + 4;
    if (chunkEnd > bytes.length) break;

    if (type === "tEXt") {
      const chunkData = bytes.subarray(dataStart, dataEnd);
      const nul = chunkData.indexOf(0);
      if (nul !== -1 && String.fromCharCode(...chunkData.subarray(0, nul)) === keyword) {
        const out = new Uint8Array(bytes.length - (chunkEnd - offset));
        out.set(bytes.subarray(0, offset), 0);
        out.set(bytes.subarray(chunkEnd), offset);
        return { bytes: out, stripped: true };
      }
    }
    if (type === "IEND") break;
    offset = chunkEnd;
  }
  return { bytes, stripped: false };
}

// Read back a tEXt chunk's value by keyword. Returns null if the file isn't
// a PNG, or the keyword isn't present (e.g. a photo that came from somewhere
// else, or one that's been recompressed since — see the note above).
async function vdReadPngText(fileOrBlob, keyword) {
  let bytes;
  try {
    bytes = new Uint8Array(await fileOrBlob.arrayBuffer());
  } catch {
    return null;
  }
  if (bytes.length < 8 || !vdIsPng(bytes)) return null;

  let offset = 8;
  while (offset + 8 <= bytes.length) {
    const length = new DataView(bytes.buffer, offset, 4).getUint32(0);
    const type = String.fromCharCode(...bytes.subarray(offset + 4, offset + 8));
    const dataStart = offset + 8;
    const dataEnd = dataStart + length;
    if (dataEnd + 4 > bytes.length) break;

    if (type === "tEXt") {
      const chunkData = bytes.subarray(dataStart, dataEnd);
      const nul = chunkData.indexOf(0);
      if (nul !== -1) {
        const chunkKeyword = String.fromCharCode(...chunkData.subarray(0, nul));
        if (chunkKeyword === keyword) {
          return String.fromCharCode(...chunkData.subarray(nul + 1));
        }
      }
    }
    if (type === "IEND") break;
    offset = dataEnd + 4; // skip CRC
  }
  return null;
}
