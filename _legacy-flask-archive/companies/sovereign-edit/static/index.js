$("create").addEventListener("click", async () => {
  $("err").classList.add("hidden");
  const res = await fetch("/works", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: $("title").value, director: $("director").value }),
  });
  const d = await res.json();
  if (!res.ok) { $("err").textContent = d.error; $("err").classList.remove("hidden"); return; }
  window.location.href = "/works/" + d.work_id;
});
