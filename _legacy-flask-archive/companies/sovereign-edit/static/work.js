let fileHash = "";
let filename = "";

$("file").addEventListener("change", async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  filename = f.name;
  $("filehash").textContent = "hashing…";
  $("filehash").classList.remove("hidden");
  fileHash = await sha256File(f);
  $("filehash").textContent = "SHA-256: " + fileHash;
});

$("addstep").addEventListener("click", async () => {
  $("err").classList.add("hidden");
  const work = $("addstep").dataset.work;
  const res = await fetch(`/works/${work}/steps`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      step_type: $("step_type").value,
      actor: $("actor").value,
      tool: $("tool").value,
      notes: $("notes").value,
      filename, file_hash: fileHash,
    }),
  });
  const d = await res.json();
  if (!res.ok) { $("err").textContent = d.error; $("err").classList.remove("hidden"); return; }
  window.location.reload();
});

document.querySelectorAll(".mark-master").forEach(btn => {
  btn.addEventListener("click", async () => {
    const res = await fetch(`/works/${btn.dataset.work}/master`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ seq: Number(btn.dataset.seq) }),
    });
    if (res.ok) window.location.reload();
  });
});
