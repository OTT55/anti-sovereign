const $ = (id) => document.getElementById(id);

// "" (Unknown) -> null, so the server sees a real tri-state, not a false "No".
function triState(id) {
  const v = $(id).value;
  return v === "" ? null : v === "true";
}

$("route").addEventListener("click", async () => {
  $("err").classList.add("hidden");
  const body = {
    asset_type: $("asset_type").value,
    value: $("value").value.replace(/[^0-9.]/g, ""),
    origin: $("origin").value,
    destination: $("destination").value,
    contains_pii: triState("contains_pii"),
    party_verified: triState("party_verified"),
    provenance_attached: triState("provenance_attached"),
  };
  const res = await fetch("/evaluate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const d = await res.json();
  if (!res.ok) { $("err").textContent = d.error; $("err").classList.remove("hidden"); return; }

  const box = $("result");
  box.classList.remove("result-ok", "result-warn", "result-bad", "result-info");
  const map = {
    ALLOW: ["ok", "✓ ALLOW", "No compliance obstacles — the transfer may proceed."],
    REVIEW: ["warn", "⚠ REVIEW", "The transfer can proceed only after the items below are resolved."],
    BLOCK: ["bad", "✗ BLOCK", "The transfer is prohibited and must not proceed."],
    INSUFFICIENT_FACTS: ["info", "◌ NEEDS INFO", "This transfer can't be fully routed yet — an Unknown flag below changes the outcome."],
  };
  const [cls, label, note] = map[d.decision];
  box.classList.add("result-" + cls);
  $("verdict").innerHTML = `<span class="badge-${cls}">${label}</span>`;
  $("c_case").textContent = d.case_id;
  $("c_time").textContent = d.created_at;
  $("c_hash").textContent = d.entry_hash;

  let html = `<p class="muted" style="font-size:13px">${note}</p>`;
  if (!d.findings.length) {
    html += `<div class="finding finding-ok">No rules fired.</div>`;
  } else {
    for (const f of d.findings) {
      const fc = f.outcome === "BLOCK" ? "bad" : (f.outcome === "INSUFFICIENT_FACTS" ? "info" : "warn");
      const cite = f.citation_url ? ` · <a href="${f.citation_url}" target="_blank" rel="noopener">source</a>` : "";
      html += `<div class="finding finding-${fc}">
        <div class="finding-title"><span class="badge-${fc}">${f.outcome}</span> ${f.rule}
          <span class="muted"> · ${f.basis}${cite}</span></div>
        <div class="finding-msg">${f.message}</div>
        ${f.remediation ? `<div class="finding-rem">→ ${f.remediation}</div>` : ""}
      </div>`;
    }
  }
  $("findings").innerHTML = html;
  box.classList.remove("hidden");
  box.scrollIntoView({ behavior: "smooth" });
});
