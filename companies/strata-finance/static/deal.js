const $ = (id) => document.getElementById(id);
const money = (c) => "$" + (c / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

$("settle").addEventListener("click", async () => {
  $("err").classList.add("hidden");
  const deal = $("settle").dataset.deal;
  const amount = $("amount").value.replace(/[^0-9.]/g, "");
  const res = await fetch(`/deals/${deal}/settle`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ amount }),
  });
  const d = await res.json();
  if (!res.ok) { $("err").textContent = d.error; $("err").classList.remove("hidden"); return; }

  $("r_id").textContent = d.settlement_id;
  $("r_gross").textContent = money(d.gross_cents);
  $("r_lines").innerHTML = d.lines.map(ln =>
    `<div class="r-line"><span>${ln.tier_label}</span><span class="party">${ln.party}</span>
     <span class="amt mono">${money(ln.amount_cents)}</span></div>`).join("") +
    (d.holdback_cents ? `<div class="r-line"><span>Holdback</span><span class="party">—</span>
     <span class="amt mono">${money(d.holdback_cents)}</span></div>` : "");
  $("receipt").classList.remove("hidden");
  // reload after a beat so the ledger + cumulative totals refresh
  setTimeout(() => window.location.reload(), 1200);
});

$("amount").addEventListener("keydown", e => { if (e.key === "Enter") $("settle").click(); });
