const $ = (id) => document.getElementById(id);
let selectedFile = null;

// ---------------------------------------------------------------------------
// Shared dropzone — one file selection feeds both verification tabs below.
// ---------------------------------------------------------------------------
const dropzone = $("dropzone");
const fileInput = $("file");

function pickFile() { fileInput.click(); }
dropzone.addEventListener("click", pickFile);
dropzone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pickFile(); }
});
["dragenter", "dragover"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("drag"); })
);
["dragleave", "drop"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.remove("drag"); })
);
dropzone.addEventListener("drop", (e) => {
  const f = e.dataTransfer.files && e.dataTransfer.files[0];
  if (f) setFile(f);
});
fileInput.addEventListener("change", (e) => {
  const f = e.target.files[0];
  if (f) setFile(f);
});
$("dz-clear").addEventListener("click", (e) => {
  e.stopPropagation();
  clearFile();
});

async function setFile(f) {
  selectedFile = f;
  fileInput.value = "";

  $("dz-empty").classList.add("hidden");
  $("dz-file").classList.remove("hidden");
  $("dz-name").textContent = f.name;
  $("dz-thumb").textContent = "◆";
  if (f.type.startsWith("image/")) {
    const url = URL.createObjectURL(f);
    $("dz-thumb").innerHTML = `<img src="${url}" alt="">`;
  } else if (f.type.startsWith("video/")) {
    $("dz-thumb").textContent = "▶";
  }

  // Informational only — the real check (below) sends the file itself now;
  // the server hashes it after stripping its own metadata chunk, so this
  // display doesn't need to match exactly (decisions/0009).
  $("filehash").textContent = "SHA-256: " + await sha256File(f);

  // If this file was captured by Veridact, its proof code is embedded right
  // in the photo (decisions/0008) — no need to separately paste it. Still
  // useful even though RECOMPRESSED (decisions/0009) no longer needs it: this
  // is what lets a genuinely-edited file correctly show ALTERED instead of
  // just UNVERIFIED.
  const embedded = await vdReadPngText(f, "veridact-manifest-id");
  if (embedded && !$("manifest_id").value.trim()) {
    $("manifest_id").value = embedded;
    $("manifest_id_note").textContent = "Found a Veridact proof code embedded in this photo — filled in automatically.";
    $("manifest_id_note").classList.remove("hidden");
  }

  $("check").disabled = false;
  $("check_c2pa").disabled = false;
  resetPanel("veridact");
  resetPanel("c2pa");
}

function clearFile() {
  selectedFile = null;
  $("dz-empty").classList.remove("hidden");
  $("dz-file").classList.add("hidden");
  $("dz-thumb").innerHTML = "◆";
  $("manifest_id_note").classList.add("hidden");
  $("check").disabled = true;
  $("check_c2pa").disabled = true;
  resetPanel("veridact");
  resetPanel("c2pa");
}

function resetPanel(which) {
  const emptyId = which === "veridact" ? "analysis-empty" : "c2pa-analysis-empty";
  const resultId = which === "veridact" ? "result" : "c2pa_result";
  const errId = which === "veridact" ? "err" : "c2pa_err";
  $(emptyId).classList.remove("hidden");
  $(resultId).classList.add("hidden");
  $(errId).classList.add("hidden");
}

// ---------------------------------------------------------------------------
// Tabs — switch which verification method is shown; each keeps its own state.
// ---------------------------------------------------------------------------
const tabs = { veridact: $("tab-veridact"), c2pa: $("tab-c2pa") };
const panels = { veridact: $("panel-veridact"), c2pa: $("panel-c2pa") };
function showTab(which) {
  Object.keys(tabs).forEach((k) => {
    const on = k === which;
    tabs[k].classList.toggle("on", on);
    tabs[k].setAttribute("aria-selected", on ? "true" : "false");
    panels[k].classList.toggle("hidden", !on);
  });
}
tabs.veridact.addEventListener("click", () => showTab("veridact"));
tabs.c2pa.addEventListener("click", () => showTab("c2pa"));
// ARIA tablist convention: arrow keys move focus and selection together.
[tabs.veridact, tabs.c2pa].forEach((btn) => {
  btn.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const other = btn === tabs.veridact ? "c2pa" : "veridact";
    showTab(other);
    tabs[other].focus();
  });
});

// ---------------------------------------------------------------------------
// Veridact manifest check
// ---------------------------------------------------------------------------
const K = (k, v) => `<div class="kv"><div class="k">${k}</div><div class="v">${v}</div></div>`;
const CMP = (label1, v1, label2, v2) => `
  <div class="ev-compare">
    <div class="ev-compare-row"><div class="k">${label1}</div><div class="v hash">${v1}</div></div>
    <div class="ev-compare-mark" aria-hidden="true">≠</div>
    <div class="ev-compare-row"><div class="k">${label2}</div><div class="v hash">${v2}</div></div>
  </div>`;

const VERDICTS = {
  VERIFIED_CAPTURE: ["ok", "✓ VERIFIED CAPTURE",
    "Signed by an enrolled device and unaltered since capture — this is a real capture."],
  RECOMPRESSED: ["info", "↻ RECOMPRESSED — CAPTURED BY VERIDACT",
    "The exact bytes don't match what was signed, but a Veridact watermark embedded at capture time was found intact. The content is very likely unchanged — it's just been re-encoded somewhere along the way (recompression, resizing, or a format change, e.g. from being sent through WhatsApp or another app). This is weaker than VERIFIED CAPTURE, which proves the exact bytes, but it's honestly different information than ALTERED below — not the same thing as a sign of tampering."],
  ALTERED: ["bad", "✗ ALTERED",
    "This came from a known device, but the file has changed since it was signed. That's often innocent: sending a photo through WhatsApp, Messenger, or some cloud syncs recompresses it, which changes the bytes without anyone editing the content. It can also mean the file was genuinely edited, re-encoded, or AI-processed. Veridact can't tell those apart from the hash alone — treat this as \"changed since capture,\" not an accusation."],
  SIGNATURE_INVALID: ["bad", "✗ SIGNATURE INVALID",
    "A manifest exists but its signature does not verify — the record was tampered with."],
  UNVERIFIED: ["warn", "? UNVERIFIED",
    "Veridact has no capture proof for this file. It may be AI-generated, or simply from a device that doesn't sign. We make no claim either way."],
};

function showLoading(analysisId) {
  $(analysisId === "analysis" ? "analysis-empty" : "c2pa-analysis-empty").classList.add("hidden");
  const resultBox = $(analysisId === "analysis" ? "result" : "c2pa_result");
  resultBox.className = "cert loading";
  resultBox.innerHTML = `<div class="ev-loading"><span class="ev-spinner" aria-hidden="true"></span>Analyzing evidence…</div>`;
  resultBox.classList.remove("hidden");
}

$("check").addEventListener("click", async () => {
  $("err").classList.add("hidden");
  if (!selectedFile) return showErr("Choose a file to verify.");
  showLoading("analysis");

  const fd = new FormData();
  fd.append("file", selectedFile);
  const mid = $("manifest_id").value.trim();
  if (mid) fd.append("manifest_id", mid);

  let res, d;
  try {
    res = await fetch("/api/verify", { method: "POST", body: fd });
    d = await res.json();
  } catch {
    $("result").classList.add("hidden");
    return showErr("Could not reach the server. If you just updated Veridact, restart the server and reload this page.");
  }
  if (!res.ok) { $("result").classList.add("hidden"); return showErr(d.error || `Server error (${res.status}).`); }

  const [cls, label, detail] = VERDICTS[d.verdict] || ["warn", d.verdict, ""];
  const box = $("result");
  box.className = "cert pop result-" + cls;

  let fields = "";
  if (d.verdict === "VERIFIED_CAPTURE" || d.verdict === "SIGNATURE_INVALID") {
    fields = K("Manifest ID", d.manifest_id) + K("Device", d.device) + K("Label", d.label) +
      K("Media SHA-256", `<span class="hash">${d.media_hash}</span>`) +
      K("Captured at", d.captured_at) + K("Received by Veridact", d.received_at || "—");
  } else if (d.verdict === "RECOMPRESSED") {
    fields = K("Manifest ID", d.manifest_id) + K("Device", d.device) + K("Label", d.label) +
      K("Captured at", d.captured_at) + K("Current file's SHA-256", `<span class="hash">${d.media_hash}</span>`);
  } else if (d.verdict === "ALTERED") {
    fields = K("Manifest ID", d.manifest_id) + K("Device", d.device) + K("Label", d.label) +
      CMP("Hash when signed", d.signed_hash, "Hash now", d.actual_hash);
  } else {
    fields = K("Media SHA-256", `<span class="hash">${d.media_hash}</span>`);
  }

  box.innerHTML = `<div class="verdict" id="verdict"><span class="badge-${cls}">${label}</span></div>
    <div id="detail" class="muted" style="font-size:13px;margin-bottom:8px">${detail}</div>
    <div id="fields">${fields}</div>`;
});

function showErr(m) {
  $("result").classList.add("hidden");
  $("analysis-empty").classList.remove("hidden");
  $("err").textContent = m;
  $("err").classList.remove("hidden");
}

// ---------------------------------------------------------------------------
// C2PA credential check: a real camera's own signature, independent of
// Veridact's own scheme above (decisions/0007). Needs the actual file — a
// C2PA manifest is embedded inside the file's own container, so there's no
// way to check it from a hash alone.
// ---------------------------------------------------------------------------
$("check_c2pa").addEventListener("click", async () => {
  $("c2pa_err").classList.add("hidden");
  if (!selectedFile) { showC2paErr("Choose a file first."); return; }
  showLoading("c2pa_analysis");

  const fd = new FormData();
  fd.append("file", selectedFile);
  let res, d;
  try {
    res = await fetch("/api/verify/c2pa", { method: "POST", body: fd });
    d = await res.json();
  } catch {
    $("c2pa_result").classList.add("hidden");
    showC2paErr("Could not reach the server. If you just updated Veridact, restart the server and reload this page.");
    return;
  }
  if (!res.ok) { $("c2pa_result").classList.add("hidden"); showC2paErr(d.error || `Server error (${res.status}).`); return; }

  const box = $("c2pa_result");

  if (!d.has_manifest) {
    box.className = "cert pop result-warn";
    box.innerHTML = `<div class="verdict"><span class="badge-warn">? NO C2PA CREDENTIAL</span></div>
      <div class="muted" style="font-size:13px">This file has no embedded C2PA manifest. It may
      still be a genuine capture — most cameras and phones don't sign with C2PA yet — Veridact
      simply makes no claim either way.</div>`;
  } else if (d.validation_state === "Valid" || d.validation_state === "Trusted") {
    box.className = "cert pop result-ok";
    box.innerHTML = `<div class="verdict"><span class="badge-ok">✓ VALID C2PA CREDENTIAL</span></div>
      <div class="muted" style="font-size:13px;margin-bottom:8px">This file carries a real,
      cryptographically valid C2PA credential.</div>
      <div>${K("Signed by (claim generator)", d.claim_generator || "—")}
        ${K("Signing certificate", (d.signature_info && d.signature_info.issuer) || "—")}
        ${K("Signed at", (d.signature_info && d.signature_info.time) || "—")}
        ${K("Assertions", (d.assertions || []).join(", ") || "—")}</div>`;
  } else {
    box.className = "cert pop result-bad";
    box.innerHTML = `<div class="verdict"><span class="badge-bad">✗ INVALID C2PA CREDENTIAL</span></div>
      <div class="muted" style="font-size:13px;margin-bottom:8px">This file has a C2PA manifest,
      but it does not validate — likely edited or corrupted since it was signed.</div>
      <div>${(d.validation_status || []).map((s) => K(s.code, s.explanation || "")).join("")}</div>`;
  }
  box.classList.remove("hidden");
});

function showC2paErr(m) {
  $("c2pa_result").classList.add("hidden");
  $("c2pa-analysis-empty").classList.remove("hidden");
  $("c2pa_err").textContent = m;
  $("c2pa_err").classList.remove("hidden");
}
