const $ = (id) => document.getElementById(id);
const chat = $("chat");

function bubble(cls, html) {
  const d = document.createElement("div");
  d.className = "msg " + cls;
  d.innerHTML = html;
  chat.appendChild(d);
  d.scrollIntoView({ behavior: "smooth", block: "end" });
  return d;
}
const esc = (s) => s.replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

async function ask(overrideQuestion) {
  const doc = $("ask").dataset.doc;
  const category = $("ask").dataset.category;
  const q = (overrideQuestion !== undefined ? overrideQuestion : $("question").value).trim();
  if (!q) return;
  $("err").classList.add("hidden");
  bubble("user", esc(q));
  if (overrideQuestion === undefined) $("question").value = "";
  const thinking = bubble("bot", "<span class='muted'>Retrieving…</span>");

  const endpoint = category ? `/collection/${category}/ask` : `/doc/${doc}/ask`;
  const res = await fetch(endpoint, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: q }),
  });
  const d = await res.json();
  if (!res.ok) { thinking.remove(); $("err").textContent = d.error; $("err").classList.remove("hidden"); return; }

  let html = `<div class="answer">${esc(d.answer).replace(/\n/g, "<br>")}</div>`;
  html += `<div class="mode-tag mode-${d.mode}">${d.mode === "generative" ? "Claude-generated" : "extractive"}</div>`;
  if (d.confidence && d.confidence.level !== "none") {
    const c = d.confidence;
    html += `<span class="conf-tag conf-${c.level}" title="top score ${c.top_score}, gap to next ${c.gap}">${c.level} confidence</span>`;
  }
  if (d.conflict && d.conflict.conflict) {
    html += `<div class="conflict-banner">⚠ Conflicting information found across sources`
      + (d.conflict.explanation ? `: ${esc(d.conflict.explanation)}` : "") + `</div>`;
  } else if (d.conflict_note) {
    html += `<div class="note">${esc(d.conflict_note)}</div>`;
  }
  if (d.note) html += `<div class="note">${esc(d.note)}</div>`;
  if (d.citations.length) {
    html += `<div class="cites"><div class="cites-h">Sources</div>` +
      d.citations.map(c =>
        `<div class="cite"><span class="cite-tag">Chunk ${c.chunk}</span>
         ${c.doc_title ? `<span class="cite-doc">${esc(c.doc_title)}</span>` : ""}
         <span class="cite-score">score ${c.score}</span>
         <div class="cite-prev">${esc(c.preview)}</div></div>`).join("") + `</div>`;
  } else {
    html += `<div class="note">No passage scored above zero — the corpus may not cover this.</div>`;
  }
  thinking.innerHTML = html;
}

$("ask").addEventListener("click", () => ask());
$("question").addEventListener("keydown", e => { if (e.key === "Enter") ask(); });

// Exposed so collection.js's structured form can submit a built question
// through the exact same ask() path as the free-form box.
window.__contextcoreAsk = ask;
