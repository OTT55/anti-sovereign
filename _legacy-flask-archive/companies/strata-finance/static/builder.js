// Strata Finance — waterfall builder.
// State lives in `parties` and `tiers`; the DOM re-renders from state on
// structural changes. Field edits update state via delegated listeners (no
// re-render, so inputs keep focus).
const $ = (id) => document.getElementById(id);
let parties = [];
let tiers = [];  // {kind:'fee', party, percent} | {kind:'recoup', party, cap} | {kind:'split', weights:{}}

function renderParties() {
  $("parties").innerHTML = parties.map((p, i) =>
    `<span class="chip">${p}<button data-i="${i}" class="chip-x" type="button">×</button></span>`).join("");
}

function partyOptions(selected) {
  return parties.map(p => `<option ${p === selected ? "selected" : ""}>${p}</option>`).join("");
}

function renderTiers() {
  // keep split weights in sync with the current participant list
  tiers.forEach(t => {
    if (t.kind === "split") {
      const w = {};
      parties.forEach(p => { w[p] = t.weights[p] ?? 0; });
      t.weights = w;
    }
  });
  $("tiers").innerHTML = tiers.map((t, i) => {
    let inner;
    if (t.kind === "fee") {
      inner = `<b>Fee</b> — <input class="pct" data-i="${i}" data-f="percent" value="${t.percent}"> % to
        <select data-i="${i}" data-f="party">${partyOptions(t.party)}</select> <span class="muted">(off the top)</span>`;
    } else if (t.kind === "recoup") {
      inner = `<b>Recoupment</b> — <select data-i="${i}" data-f="party">${partyOptions(t.party)}</select>
        up to $<input class="cap" data-i="${i}" data-f="cap" value="${t.cap}">`;
    } else {
      inner = `<b>Backend split</b><div class="split-grid">` +
        parties.map(p => `<label class="split-cell">${p}
          <input class="pct" data-i="${i}" data-f="w:${p}" value="${t.weights[p]}"> %</label>`).join("") +
        `</div>`;
    }
    return `<div class="tier-row"><span class="tier-idx">${i + 1}</span>
      <div class="tier-content">${inner}</div>
      <button class="chip-x" data-remove="${i}" type="button">×</button></div>`;
  }).join("");
}

// --- participants ---
$("add_party").addEventListener("click", () => {
  const v = $("new_party").value.trim();
  if (v && !parties.includes(v)) { parties.push(v); $("new_party").value = ""; renderParties(); renderTiers(); }
});
$("new_party").addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); $("add_party").click(); } });
$("parties").addEventListener("click", e => {
  if (e.target.dataset.i !== undefined) { parties.splice(+e.target.dataset.i, 1); renderParties(); renderTiers(); }
});

// --- tiers ---
$("add_fee").addEventListener("click", () => { tiers.push({ kind: "fee", party: parties[0] || "", percent: 10 }); renderTiers(); });
$("add_recoup").addEventListener("click", () => { tiers.push({ kind: "recoup", party: parties[0] || "", cap: 100000 }); renderTiers(); });
$("add_split").addEventListener("click", () => { tiers.push({ kind: "split", weights: {} }); renderTiers(); });

$("tiers").addEventListener("input", e => {
  const i = e.target.dataset.i, f = e.target.dataset.f;
  if (i === undefined || !f) return;
  const t = tiers[+i];
  if (f === "percent") t.percent = e.target.value;
  else if (f === "cap") t.cap = e.target.value;
  else if (f === "party") t.party = e.target.value;
  else if (f.startsWith("w:")) t.weights[f.slice(2)] = e.target.value;
});
$("tiers").addEventListener("change", e => {
  const i = e.target.dataset.i, f = e.target.dataset.f;
  if (f === "party" && i !== undefined) tiers[+i].party = e.target.value;
});
$("tiers").addEventListener("click", e => {
  if (e.target.dataset.remove !== undefined) { tiers.splice(+e.target.dataset.remove, 1); renderTiers(); }
});

// --- example ---
$("load_example").addEventListener("click", () => {
  parties = ["Distributor", "Investor", "OTT (Director)"];
  tiers = [
    { kind: "fee", party: "Distributor", percent: 15 },
    { kind: "recoup", party: "Investor", cap: 250000 },
    { kind: "split", weights: { "Distributor": 0, "Investor": 40, "OTT (Director)": 60 } },
  ];
  $("deal_name").value = "The Long Take — distribution deal";
  renderParties(); renderTiers();
});

// --- submit ---
$("create").addEventListener("click", async () => {
  $("err").classList.add("hidden");
  const payload = { name: $("deal_name").value.trim(), tiers: tiers.map(t => {
    if (t.kind === "fee") return { kind: "fee", party: t.party, percent: parseFloat(t.percent) || 0 };
    if (t.kind === "recoup") return { kind: "recoup", party: t.party, cap_cents: Math.round((parseFloat(t.cap) || 0) * 100) };
    const weights = {}; for (const p in t.weights) weights[p] = parseFloat(t.weights[p]) || 0;
    return { kind: "split", weights };
  }) };
  const res = await fetch("/deals", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });
  const d = await res.json();
  if (!res.ok) { $("err").textContent = d.error; $("err").classList.remove("hidden"); return; }
  window.location.href = "/deals/" + d.deal_id;
});
