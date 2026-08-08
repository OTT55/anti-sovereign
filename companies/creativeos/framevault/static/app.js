/* ==========================================================================
 * FrameVault — shared front-end helpers
 * No framework, no build step. Loaded on every page.
 * ========================================================================== */

/* ----- theme (persisted, respects system preference on first visit) ------ */
(function initTheme() {
  const saved = localStorage.getItem("fv-theme");
  const system = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", saved || system);
})();

function toggleTheme() {
  const cur = document.documentElement.getAttribute("data-theme");
  const next = cur === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("fv-theme", next);
  paintThemeIcon();
}

function paintThemeIcon() {
  const el = document.getElementById("theme-icon");
  if (!el) return;
  const dark = document.documentElement.getAttribute("data-theme") === "dark";
  el.textContent = dark ? "☀" : "☾";
}
document.addEventListener("DOMContentLoaded", paintThemeIcon);

/* ----- mobile nav (nav-links collapses behind this below 680px) ---------- */
function toggleNav() {
  const links = document.getElementById("navLinks");
  const btn = document.getElementById("navToggle");
  if (!links || !btn) return;
  const open = links.classList.toggle("open");
  btn.setAttribute("aria-expanded", open ? "true" : "false");
}
document.addEventListener("click", (e) => {
  const links = document.getElementById("navLinks");
  const btn = document.getElementById("navToggle");
  if (!links || !links.classList.contains("open")) return;
  if (links.contains(e.target) || (btn && btn.contains(e.target))) return;
  links.classList.remove("open");
  if (btn) btn.setAttribute("aria-expanded", "false");
});

/* ----- toasts ------------------------------------------------------------ */
function toast(msg, kind) {
  let host = document.getElementById("toasts");
  if (!host) {
    host = document.createElement("div");
    host.id = "toasts";
    document.body.appendChild(host);
  }
  const t = document.createElement("div");
  t.className = "toast" + (kind ? " " + kind : "");
  t.textContent = msg;
  host.appendChild(t);
  setTimeout(() => {
    t.style.transition = "opacity .3s, transform .3s";
    t.style.opacity = "0";
    t.style.transform = "translateY(8px)";
    setTimeout(() => t.remove(), 300);
  }, 2600);
}

/* ----- real SHA-256 of a File, computed in the browser (Web Crypto) ------ *
 * The file never leaves the device — only its 64-char fingerprint does.     */
async function sha256File(file) {
  const buf = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buf);
  return [...new Uint8Array(digest)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/* ----- fetch helpers ----------------------------------------------------- */
async function postJSON(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await r.json().catch(() => ({}));
  return { ok: r.ok, status: r.status, data };
}

async function del(url) {
  const r = await fetch(url, { method: "DELETE" });
  return { ok: r.ok, status: r.status, data: await r.json().catch(() => ({})) };
}

/* ----- clipboard --------------------------------------------------------- */
async function copyText(text, label) {
  try {
    await navigator.clipboard.writeText(text);
    toast((label || "Copied") + " to clipboard", "ok");
  } catch {
    toast("Couldn't copy — select and copy manually", "err");
  }
}

/* ----- small utils ------------------------------------------------------- */
function fmtBytes(n) {
  n = Number(n) || 0;
  if (!n) return "";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n < 10 && i > 0 ? 1 : 0)} ${u[i]}`;
}

function shortHash(h) {
  return h ? h.slice(0, 10) + "…" + h.slice(-8) : "";
}

/* ---- command palette (Ctrl/Cmd+K) — searches /api/search live -------------
   Read-only, additive endpoint; doesn't touch any existing route. */
(function () {
  let selIdx = 0, results = [], debounceTimer = null;

  function els() {
    return {
      scrim: document.getElementById("paletteScrim"),
      panel: document.getElementById("palette"),
      input: document.getElementById("paletteInput"),
      list: document.getElementById("paletteResults"),
    };
  }

  window.openPalette = function () {
    const { scrim, panel, input } = els();
    if (!scrim || !panel) return;
    scrim.classList.remove("hidden");
    panel.classList.remove("hidden");
    input.value = "";
    renderResults([]);
    input.focus();
  };
  window.closePalette = function () {
    const { scrim, panel } = els();
    if (scrim) scrim.classList.add("hidden");
    if (panel) panel.classList.add("hidden");
  };

  function renderResults(list) {
    results = list; selIdx = 0;
    const { list: host } = els();
    if (!host) return;
    if (!list.length) {
      host.innerHTML = '<div class="palette-empty">Type to search creators and registered works…</div>';
      return;
    }
    host.innerHTML = list.map((r, i) =>
      `<a class="palette-row${i === 0 ? " sel" : ""}" href="${r.url}" data-i="${i}">
         <span class="palette-type">${r.type}</span>
         <span class="palette-title">${r.title}</span>
         <span class="palette-sub">${r.subtitle || ""}</span>
       </a>`
    ).join("");
  }

  function highlight() {
    const { list: host } = els();
    if (!host) return;
    [...host.querySelectorAll(".palette-row")].forEach((el, i) => el.classList.toggle("sel", i === selIdx));
  }

  async function runSearch(q) {
    if (!q.trim()) { renderResults([]); return; }
    try {
      const r = await fetch("/api/search?q=" + encodeURIComponent(q));
      const data = await r.json();
      renderResults(data.results || []);
    } catch (e) { /* offline — leave last results in place */ }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const { input } = els();
    if (!input) return;
    input.addEventListener("input", () => {
      clearTimeout(debounceTimer);
      const q = input.value;
      debounceTimer = setTimeout(() => runSearch(q), 150);
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") { e.preventDefault(); selIdx = Math.min(selIdx + 1, results.length - 1); highlight(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); selIdx = Math.max(selIdx - 1, 0); highlight(); }
      else if (e.key === "Enter") { e.preventDefault(); const r = results[selIdx]; if (r) window.location.href = r.url; }
      else if (e.key === "Escape") { closePalette(); }
    });
  });

  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      const { panel } = els();
      if (panel && !panel.classList.contains("hidden")) closePalette(); else openPalette();
    } else if (e.key === "Escape") {
      const { panel } = els();
      if (panel && !panel.classList.contains("hidden")) closePalette();
    }
  });
})();
