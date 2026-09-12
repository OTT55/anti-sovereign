const $ = (id) => document.getElementById(id);
let genre = window.GENRES[0].key;
let lastAdapted = "";

const storyByKey = Object.fromEntries(window.STORIES.map(s => [s.key, s]));
const genreLabel = Object.fromEntries(window.GENRES.map(g => [g.key, g.label]));

function showOriginal() {
  const s = storyByKey[$("story").value];
  $("original").textContent = s.text;
  $("src-meta").textContent = "· " + s.source;
}
$("story").addEventListener("change", showOriginal);
showOriginal();

$("genres").addEventListener("click", (e) => {
  if (!e.target.dataset.genre) return;
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  e.target.classList.add("active");
  genre = e.target.dataset.genre;
});

$("adapt").addEventListener("click", async () => {
  $("err").classList.add("hidden");
  $("download").classList.add("hidden");
  $("genre-tag").textContent = genreLabel[genre];
  $("adapted").innerHTML = '<span class="muted">Adapting with Claude…</span>';
  $("adapt").disabled = true;

  const res = await fetch("/adapt", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ story: $("story").value, genre }),
  });
  const d = await res.json();
  $("adapt").disabled = false;

  if (!res.ok) {
    $("adapted").innerHTML = '<span class="muted">No adaptation — see the message below.</span>';
    $("err").innerHTML = (d.blocked ? "⚠ " : "") + d.error +
      (d.blocked ? '<br><span class="muted">The engine is wired to Claude; add API credit at console.anthropic.com to run live adaptations.</span>' : "");
    $("err").classList.remove("hidden");
    return;
  }
  lastAdapted = d.adapted;
  $("adapted").textContent = d.adapted;
  $("download").classList.remove("hidden");
});

$("download").addEventListener("click", () => {
  const s = storyByKey[$("story").value];
  const blob = new Blob([lastAdapted], { type: "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${s.key}-${genre}.txt`;
  a.click();
});
