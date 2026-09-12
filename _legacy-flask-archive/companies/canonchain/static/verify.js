const $ = (id) => document.getElementById(id);

function renderProof(container, proof) {
  container.innerHTML = "";
  if (!proof.length) {
    container.innerHTML = '<div class="proof-step">Root leaf — the registry currently holds a single work.</div>';
    return;
  }
  proof.forEach((s, i) => {
    const d = document.createElement("div");
    d.className = "proof-step";
    d.innerHTML = `${i + 1}. combine with <span class="pos">${s.position}</span> sibling → ${s.hash}`;
    container.appendChild(d);
  });
}

$("check").addEventListener("click", async () => {
  $("err").classList.add("hidden");
  $("cert").classList.add("hidden");
  $("none").classList.add("hidden");
  const hash = $("hashinput").value.trim().toLowerCase();
  const res = await fetch("/api/verify?hash=" + encodeURIComponent(hash));
  const data = await res.json();
  if (!res.ok) {
    $("err").textContent = data.error;
    $("err").classList.remove("hidden");
    return;
  }
  if (!data.registered) {
    $("none").classList.remove("hidden");
    return;
  }
  const v = $("verdict");
  if (data.inclusion_verified) {
    v.innerHTML = '<span class="badge-ok">✓ Inclusion proof valid</span> — this hash is provably part of the registry root.';
  } else {
    v.innerHTML = '<span class="badge-bad">✗ Inclusion proof failed</span> — registry inconsistency detected.';
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
});

$("hashinput").addEventListener("keydown", (e) => { if (e.key === "Enter") $("check").click(); });
