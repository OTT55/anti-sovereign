// Client-side SHA-256 via Web Crypto — the file itself never leaves the browser.
const $ = (id) => document.getElementById(id);
let currentHash = null;

async function sha256(file) {
  const buf = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buf);
  return [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, "0")).join("");
}

$("file").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  $("filename").value = file.name;
  $("hashline").textContent = "hashing…";
  $("hashline").classList.remove("hidden");
  currentHash = await sha256(file);
  $("hashline").textContent = "SHA-256: " + currentHash;
  $("submit").disabled = false;
});

function renderProof(container, proof) {
  container.innerHTML = "";
  if (!proof.length) {
    container.innerHTML = '<div class="proof-step">Root leaf — the tree currently holds a single work.</div>';
    return;
  }
  proof.forEach((s, i) => {
    const d = document.createElement("div");
    d.className = "proof-step";
    d.innerHTML = `${i + 1}. combine with <span class="pos">${s.position}</span> sibling → ${s.hash}`;
    container.appendChild(d);
  });
}

$("submit").addEventListener("click", async () => {
  $("err").classList.add("hidden");
  const body = {
    file_hash: currentHash,
    filename: $("filename").value,
    creator_name: $("creator").value,
    description: $("description").value,
  };
  const res = await fetch("/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) {
    let msg = data.error;
    if (data.registry_id) msg += ` (already ${data.registry_id}, by ${data.creator_name})`;
    $("err").textContent = msg;
    $("err").classList.remove("hidden");
    return;
  }
  $("c_id").textContent = data.registry_id;
  $("c_creator").textContent = data.creator_name;
  $("c_file").textContent = data.filename;
  $("c_hash").textContent = data.file_hash;
  $("c_time").textContent = data.created_at;
  $("c_root").textContent = data.merkle_root;
  $("c_index").textContent = data.leaf_index;
  $("c_size").textContent = data.registry_size;
  renderProof($("c_proof"), data.proof);
  $("cert").classList.remove("hidden");
  $("cert").scrollIntoView({ behavior: "smooth" });

  // the registry just grew — reflect that in the header stats immediately,
  // not just inside the certificate
  pulseStat($("stat-count"), String(data.registry_size));
  pulseStat($("stat-root"), data.merkle_root.slice(0, 16) + "…");
});

function pulseStat(el, text) {
  if (!el || el.textContent === text) return;
  el.textContent = text;
  el.classList.remove("pulse");
  void el.offsetWidth;
  el.classList.add("pulse");
}

// the registry is shared — another tab, another user, even another OTT
// product could register a work between page loads. Poll quietly so the
// numbers on screen are never stale for long, matching the "living registry"
// identity rather than a static snapshot.
async function pollStats() {
  try {
    const res = await fetch("/api/stats");
    if (!res.ok) return;
    const data = await res.json();
    pulseStat($("stat-count"), String(data.count));
    pulseStat($("stat-root"), (data.root || "—").slice(0, 16) + (data.root ? "…" : ""));
  } catch (e) { /* offline — skip this tick */ }
}
setInterval(pollStats, 12000);
