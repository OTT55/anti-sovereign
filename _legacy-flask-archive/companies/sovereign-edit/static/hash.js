// Client-side SHA-256 via Web Crypto. Files are fingerprinted in the browser —
// your footage never uploads, which matters when the files are 40GB masters.
async function sha256File(file) {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, "0")).join("");
}

const $ = (id) => document.getElementById(id);
