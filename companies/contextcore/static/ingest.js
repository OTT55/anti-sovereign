const $ = (id) => document.getElementById(id);

$("ingest").addEventListener("click", async () => {
  $("err").classList.add("hidden");
  const fd = new FormData();
  fd.append("title", $("title").value.trim());
  fd.append("text", $("text").value);
  if ($("file").files[0]) fd.append("file", $("file").files[0]);
  $("ingest").disabled = true;
  $("ingest").textContent = "Indexing…";
  const res = await fetch("/ingest", { method: "POST", body: fd });
  const d = await res.json();
  $("ingest").disabled = false;
  $("ingest").textContent = "Ingest & index";
  if (!res.ok) { $("err").textContent = d.error; $("err").classList.remove("hidden"); return; }
  window.location.href = "/doc/" + d.doc_id;
});
