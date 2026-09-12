const K = (k, v) => `<div class="kv"><div class="k">${k}</div><div class="v">${v}</div></div>`;

const VERDICTS = {
  APPROVED_MASTER: ["ok", "✓ APPROVED MASTER",
    "This is the cut that was signed off. Safe to send."],
  NOT_THE_MASTER: ["warn", "⚠ NOT THE MASTER",
    "This file is part of the production, but it is an earlier stage — not the approved master."],
  IN_LINEAGE: ["warn", "• IN LINEAGE",
    "This file is part of the production, but no master has been designated for this work yet."],
  UNKNOWN: ["bad", "✗ NOT IN THE ARCHIVE",
    "Sovereign Edit has never seen this file. It isn't a recorded step of any tracked work."],
};

$("file").addEventListener("change", async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  $("err").classList.add("hidden");
  $("result").classList.add("hidden");
  $("filehash").textContent = "hashing…";
  $("filehash").classList.remove("hidden");
  const hash = await sha256File(f);
  $("filehash").textContent = "SHA-256: " + hash;

  const res = await fetch("/api/identify?hash=" + encodeURIComponent(hash));
  const d = await res.json();
  if (!res.ok) { $("err").textContent = d.error; $("err").classList.remove("hidden"); return; }

  const [cls, label, detail] = VERDICTS[d.verdict];
  const box = $("result");
  box.classList.remove("result-ok", "result-bad", "result-warn");
  box.classList.add("result-" + cls);
  $("verdict").innerHTML = `<span class="badge-${cls}">${label}</span>`;
  $("detail").textContent = detail;

  let fields = "";
  if (d.found) {
    fields += K("Work", `${d.title} · dir. ${d.director}`);
    fields += K("This file is", `Step #${d.step.seq} — ${d.step.step_type}` +
      (d.step.actor ? ` <span class="muted">by ${d.step.actor}</span>` : ""));
    if (d.step.filename) fields += K("Filed as", `<span class="mono">${d.step.filename}</span>`);
    fields += K("Logged at (UTC)", d.step.created_at);
    if (d.verdict === "NOT_THE_MASTER" && d.master) {
      fields += K("The approved master is",
        `Step #${d.master.seq} — ${d.master.step_type}` +
        (d.master.filename ? ` <span class="mono">(${d.master.filename})</span>` : ""));
    }
    fields += K("Lineage", d.chain_intact
      ? `<span class="badge-ok">intact</span> — ${d.step_count} steps`
      : `<span class="badge-bad">BROKEN at step #${d.chain_broken_at}</span>`);
    fields += K("Work ID", `<a href="/works/${d.work_id}" class="mono">${d.work_id}</a>`);
  } else {
    fields += K("SHA-256", `<span class="hash">${d.file_hash}</span>`);
  }
  $("fields").innerHTML = fields;
  box.classList.remove("hidden");
});
