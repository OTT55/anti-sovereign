/* Story Atlas — front-end workspace.
   Vanilla JS SPA: fetches from the Flask API, renders each view, and drives the
   relationship graph, canon warnings, and AI assistant. No framework, no build. */

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => (s == null ? "" : String(s).replace(/[&<>"]/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])));

const State = { universes: [], uid: null, universe: null, overview: null, aiLog: [] };

async function api(path, opts) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts && opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || res.statusText);
  return res.json();
}

const initials = (name) => name.split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join("").toUpperCase();

/* ------------------------------------------------------------------ boot */
async function boot() {
  wireNav();
  State.universes = await api("/api/universes");
  renderUniverseSwitcher();
  if (!State.universes.length) { showEmptyWorkspace(); return; }
  State.uid = State.universes[0].id;
  await loadUniverse();
  go("dashboard");
}

function showEmptyWorkspace() {
  State.uid = null; State.universe = null;
  $("#universeName").textContent = "No universe";
  $$("[data-count]").forEach(el => { el.textContent = ""; });
  $("#canonBadge").textContent = "";
  currentView = "dashboard";
  $$("#nav .nav-item").forEach(a => a.classList.remove("active"));
  $("#main").innerHTML = `<div class="page"><div class="empty-view"><div class="big">✦</div>
    No universes yet.<div style="margin-top:14px"><button class="btn primary" id="firstUniverse">+ New universe</button></div></div></div>`;
  $("#firstUniverse").addEventListener("click", openNewUniverse);
}

async function loadUniverse() {
  State.universe = State.universes.find(u => u.id === State.uid);
  $("#universeName").textContent = State.universe.name;
  State.overview = await api(`/api/universes/${State.uid}/overview`);
  // sidebar counts + canon badge
  const c = State.overview.counts;
  $$("[data-count]").forEach(el => { el.textContent = c[el.dataset.count] ?? ""; });
  const badge = $("#canonBadge");
  badge.textContent = State.overview.warning_count || "";
}

/* ------------------------------------------------------------ nav / router */
function wireNav() {
  $$("#nav .nav-item").forEach(a => a.addEventListener("click", () => go(a.dataset.view)));
  $("#universeButton").addEventListener("click", (e) => {
    e.stopPropagation(); $("#universeMenu").classList.toggle("hidden");
  });
  document.addEventListener("click", () => $("#universeMenu").classList.add("hidden"));
  $("#modalHost").addEventListener("click", (e) => {
    if (e.target.dataset.close !== undefined) closeModal();
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });
}

function renderUniverseSwitcher() {
  const menu = $("#universeMenu");
  menu.innerHTML = State.universes.map(u => `
    <div class="universe-row">
      <a data-uid="${u.id}">${esc(u.name)}<small>${esc(u.genre || "Universe")}</small></a>
      <button class="universe-del" data-del="${u.id}" title="Delete universe">×</button>
    </div>`).join("")
    + `<div class="divider"></div>`
    + `<a class="newu" id="newUniverse">+ New universe</a>`
    + `<a class="newu" id="newFromDraft">+ New universe from draft…</a>`
    + (State.universes.length ? `<a class="newu" id="importDraft">⇪ Add draft to existing universe…</a>` : "")
    + (State.uid ? `<a class="newu" id="editDraft">✎ Edit a previous draft…</a>` : "");
  $$("a[data-uid]", menu).forEach(a => a.addEventListener("click", async () => {
    State.uid = +a.dataset.uid; $("#universeMenu").classList.add("hidden");
    await loadUniverse(); go(currentView);
  }));
  $$("[data-del]", menu).forEach(btn => btn.addEventListener("click", (e) => {
    e.stopPropagation();
    deleteUniverse(+btn.dataset.del);
  }));
  $("#newUniverse").addEventListener("click", openNewUniverse);
  $("#newFromDraft").addEventListener("click", openNewUniverseFromDraft);
  const importBtn = $("#importDraft");
  if (importBtn) importBtn.addEventListener("click", openPickUniverseForDraft);
  const editBtn = $("#editDraft");
  if (editBtn) editBtn.addEventListener("click", openEditPreviousDraft);
}

async function openEditPreviousDraft() {
  $("#universeMenu").classList.add("hidden");
  const drafts = await api(`/api/universes/${State.uid}/drafts`);
  if (!drafts.length) {
    modal(`<div class="modal-head"><div><h2>Edit a previous draft</h2></div>
        <button class="modal-x" data-close>×</button></div>
      <div class="modal-body"><div class="ai-a empty">No drafts saved for this universe yet — importing
        one from the universe menu keeps a copy here to come back to.</div></div>`);
    $$("[data-close]", $("#modalBody")).forEach(b => b.addEventListener("click", closeModal));
    return;
  }
  modal(`<div class="modal-head"><div><h2>Edit a previous draft</h2>
      <div class="sub">Pick one to reopen and revise. Re-importing reuses existing characters, places,
        and events by name — nothing gets duplicated for anything that didn't change.</div></div>
      <button class="modal-x" data-close>×</button></div>
    <div class="modal-body"><div class="rel-list">${drafts.map(d => `
      <div class="rel-row draft-pick" data-did="${d.id}" style="cursor:pointer">
        <span>${esc(d.preview)}</span>
        <span style="margin-left:auto;color:var(--text-3);font-size:12px">${esc(d.created_at.slice(0, 10))}</span>
      </div>`).join("")}</div></div>`);
  $$("[data-close]", $("#modalBody")).forEach(b => b.addEventListener("click", closeModal));
  $$("[data-did]", $("#modalBody")).forEach(row => row.addEventListener("click", async () => {
    const draft = await api(`/api/drafts/${row.dataset.did}`);
    openImportDraft(State.uid, State.universe.name, draft.content);
  }));
}

async function deleteUniverse(uid) {
  const u = State.universes.find(x => x.id === uid);
  if (!u) return;
  if (!confirm(`Delete "${u.name}"? This removes every character, scene, event, and relationship in it. This cannot be undone.`)) return;
  await api(`/api/universes/${uid}`, { method: "DELETE" });
  State.universes = State.universes.filter(x => x.id !== uid);
  $("#universeMenu").classList.add("hidden");
  renderUniverseSwitcher();
  if (!State.universes.length) { showEmptyWorkspace(); return; }
  if (State.uid === uid) State.uid = State.universes[0].id;
  await loadUniverse();
  go(currentView);
}

let currentView = "dashboard";
function go(view) {
  if (!State.uid) { showEmptyWorkspace(); return; }
  currentView = view;
  $$("#nav .nav-item").forEach(a => a.classList.toggle("active", a.dataset.view === view));
  const main = $("#main");
  main.scrollTop = 0;
  ({
    dashboard: viewDashboard, characters: viewCharacters, timeline: viewTimeline,
    locations: viewLocations, organizations: viewOrganizations, graph: viewGraph,
    lore: viewLore, scenes: viewScenes, assistant: viewAssistant, canon: viewCanon,
  }[view] || viewDashboard)(main);
}

function head(eyebrow, title, sub, actions = "") {
  return `<div class="page-head"><div class="page-head-row"><div>
    <div class="eyebrow">${esc(eyebrow)}</div>
    <h1 class="page-title">${esc(title)}</h1>
    ${sub ? `<div class="page-sub">${esc(sub)}</div>` : ""}
    </div><div>${actions}</div></div></div>`;
}

/* --------------------------------------------------------------- Dashboard */
async function viewDashboard(main) {
  const o = State.overview = await api(`/api/universes/${State.uid}/overview`);
  const u = o.universe, c = o.counts;
  const span = o.span && o.span.lo != null ? `${u.era_label} ${o.span.lo}–${o.span.hi}` : "—";
  const stat = (n, l, cls, icon, view) =>
    `<div class="stat c-${cls}" data-go="${view}"><span class="icon">${icon}</span>
      <div class="n">${n}</div><div class="l">${l}</div></div>`;

  main.innerHTML = `<div class="page">
    <div class="hero">
      <span class="genre">${esc(u.genre || "Universe")}</span>
      <h1>${esc(u.name)}</h1>
      <p>${esc(u.summary || "A universe under construction.")}</p>
      <div style="margin-top:16px">
        ${u.published_at
          ? `<span class="tag" style="border-color:var(--accent);color:var(--accent-2)">Published by @${esc(u.published_by)}</span>`
          : `<button class="btn primary sm" id="publishBtn">Publish to FrameVault</button>`}
      </div>
    </div>

    <div class="stat-grid">
      ${stat(c.characters, "Characters", "character", "☺", "characters")}
      ${stat(c.locations, "Locations", "location", "⌖", "locations")}
      ${stat(c.organizations, "Organizations", "organization", "⬡", "organizations")}
      ${stat(c.events, "Timeline events", "event", "◷", "timeline")}
    </div>

    <div class="cols">
      <div class="panel">
        <h3>Key events <span class="r">${span}</span></h3>
        <div class="mini-list">
          ${o.key_events.length ? o.key_events.map(e => `
            <div class="mini-item" data-event="${e.id}">
              <span class="yr">${u.era_label} ${e.year ?? "—"}</span>
              <span class="tt">${esc(e.title)}<small>${esc(e.description || "")}</small></span>
              <span class="tag cat-${esc(e.category)}">${esc(e.category || "event")}</span>
            </div>`).join("") : "<div class='ai-a empty'>No events yet.</div>"}
        </div>
      </div>

      <div class="panel">
        <h3>Canon Engine <span class="r">${o.warning_count} open</span></h3>
        ${o.warnings.length ? o.warnings.slice(0, 4).map(warnCard).join("")
          : `<div class="clean-state"><div class="big">✓</div>Canon is consistent.</div>`}
        ${o.warning_count > 4 ? `<a class="btn ghost sm" data-go="canon" style="margin-top:8px">View all ${o.warning_count} →</a>` : ""}
      </div>
    </div>

    <div class="panel" style="margin-top:18px">
      <h3>Recently added</h3>
      <div class="mini-list">
        ${o.recent.map(r => `<div class="mini-item" data-character="${r.id}">
          <span class="avatar t-character" style="width:28px;height:28px;flex:0 0 28px;font-size:11px">${initials(r.name)}</span>
          <span class="tt">${esc(r.name)}</span><span class="tag">character</span></div>`).join("")}
      </div>
    </div>
  </div>`;

  $$("[data-go]", main).forEach(el => el.addEventListener("click", () => go(el.dataset.go)));
  $$("[data-character]", main).forEach(el => el.addEventListener("click", () => openCharacter(+el.dataset.character)));
  $$("[data-event]", main).forEach(el => el.addEventListener("click", () => go("timeline")));
  const publishBtn = $("#publishBtn", main);
  if (publishBtn) publishBtn.addEventListener("click", publishUniverse);
}

async function publishUniverse() {
  let data;
  try {
    data = await api(`/api/universes/${State.uid}/publish`, { method: "POST" });
  } catch (e) {
    alert(e.message);
    return;
  }
  modal(`<div class="modal-head"><div><h2>${data.credited ? "Published — and the credit landed." : "Published."}</h2></div>
      <button class="modal-x" data-close>×</button></div>
    <div class="modal-body">
      <p style="color:var(--text-2);font-size:13.5px;line-height:1.6">${
        data.credited
          ? `A verified <code>canon.published</code> credit was written to your FrameVault.`
          : esc(data.note || "")
      }</p>
      ${data.credited ? `<div class="form-actions">
        <a class="btn primary" href="${data.public_url}" target="_blank" rel="noopener">See your profile &#8599;</a>
      </div>` : ""}
    </div>`);
  $$("[data-close]", $("#modalBody")).forEach(b => b.addEventListener("click", closeModal));
  await loadUniverse();
  await go("dashboard");
}

/* -------------------------------------------------------------- Characters */
let charState = { all: [], q: "", filter: "all" };
async function viewCharacters(main) {
  main.innerHTML = head("Database", "Characters",
    "Every person in the universe — identity, narrative drive, relationships, and story presence.",
    `<button class="btn primary" id="addChar">+ New character</button>`)
    + `<div class="toolbar">
        <input class="search" id="charSearch" placeholder="Search characters…">
        <div class="chips" id="charFilters">
          <button class="chip active" data-f="all">All</button>
          <button class="chip" data-f="alive">Alive</button>
          <button class="chip" data-f="dead">Deceased</button>
        </div>
       </div>
       <div class="card-grid" id="charGrid"></div>`;
  charState.all = await api(`/api/universes/${State.uid}/characters`);
  $("#addChar").addEventListener("click", openNewCharacter);
  $("#charSearch").addEventListener("input", e => { charState.q = e.target.value.toLowerCase(); renderCharGrid(); });
  $$("#charFilters .chip").forEach(ch => ch.addEventListener("click", () => {
    $$("#charFilters .chip").forEach(c => c.classList.remove("active"));
    ch.classList.add("active"); charState.filter = ch.dataset.f; renderCharGrid();
  }));
  renderCharGrid();
}
function renderCharGrid() {
  const list = charState.all.filter(c => {
    if (charState.filter === "alive" && c.status === "dead") return false;
    if (charState.filter === "dead" && c.status !== "dead") return false;
    if (charState.q && !(`${c.name} ${c.role}`.toLowerCase().includes(charState.q))) return false;
    return true;
  });
  const grid = $("#charGrid");
  if (!list.length) { grid.innerHTML = `<div class="empty-view" style="grid-column:1/-1"><div class="big">☺</div>No characters match.</div>`; return; }
  grid.innerHTML = list.map(c => `
    <div class="card" data-character="${c.id}">
      ${c.status === "dead" ? '<span class="badge-dead">✝</span>' : ""}
      <div class="card-top">
        <div class="avatar t-character">${initials(c.name)}</div>
        <div><div class="nm">${esc(c.name)}</div><div class="role">${esc(c.role || "—")}</div></div>
      </div>
      <div class="desc">${esc(c.biography || c.personality || "No biography yet.")}</div>
      <div class="meta">
        ${c.age ? `<span class="pill">Age ${esc(c.age)}</span>` : ""}
        <span class="pill ${c.status === "dead" ? "dead" : "alive"}">${c.status === "dead" ? "Deceased" : "Alive"}</span>
        ${c.goals ? `<span class="pill">Goal-driven</span>` : ""}
      </div>
    </div>`).join("");
  $$("[data-character]", grid).forEach(el => el.addEventListener("click", () => openCharacter(+el.dataset.character)));
}

async function openCharacter(id) {
  const c = await api(`/api/characters/${id}`);
  const f = (lab, val) => val ? `<div class="field"><div class="lab">${lab}</div><div class="val">${esc(val)}</div></div>` : "";
  const life = [c.birth_year != null ? `b. ${c.birth_year}` : null, c.death_year != null ? `d. ${c.death_year}` : null].filter(Boolean).join(" · ");
  const rels = c.relationships.length ? `<div class="section-label">Relationships</div><div class="rel-list">${
    c.relationships.map(r => `<div class="rel-row" ${r.type === "character" ? `data-character="${r.id}"` : ""} style="cursor:${r.type === "character" ? "pointer" : "default"}">
      <span class="rk ${esc(r.kind)}">${esc(r.kind)}</span>
      <span>${esc(r.name)}</span>
      <span style="margin-left:auto;color:var(--text-3);font-size:12px">${esc(r.label || r.type)}</span></div>`).join("")}</div>` : "";
  const scenes = c.scenes.length ? `<div class="section-label">Story presence — ${c.scenes.length} scene(s)</div><div class="rel-list">${
    c.scenes.map(s => `<div class="rel-row"><span class="rk member">scene</span><span>${esc(s.title)}</span>
      <span style="margin-left:auto;color:var(--text-3);font-size:12px">${s.time_year != null ? "AE " + s.time_year : ""}</span></div>`).join("")}</div>` : "";

  modal(`
    <div class="modal-head">
      <div class="avatar t-character">${initials(c.name)}</div>
      <div><h2>${esc(c.name)}</h2><div class="sub">${esc(c.role || "Character")}${life ? " · " + esc(life) : ""}</div></div>
      <button class="modal-x" data-close>×</button>
    </div>
    <div class="modal-body">
      <div class="field-grid">
        ${f("Age", c.age)}${f("Status", c.status === "dead" ? "Deceased" : c.status)}
      </div>
      ${f("Appearance", c.appearance)}
      ${f("Biography", c.biography)}
      ${f("Personality", c.personality)}
      <div class="section-label">Narrative</div>
      <div class="field-grid">${f("Goals", c.goals)}${f("Motivations", c.motivations)}${f("Fears", c.fears)}${f("Conflicts", c.conflicts)}</div>
      ${f("Character arc", c.arc)}
      ${rels}${scenes}
      <div class="form-actions" style="margin-top:22px">
        <button class="btn danger" id="deleteChar">Delete</button>
        <button class="btn" id="editChar">Edit</button>
      </div>
    </div>`);
  $$("[data-character]", $("#modalBody")).forEach(el => el.addEventListener("click", () => openCharacter(+el.dataset.character)));
  $("#editChar").addEventListener("click", () => openEditCharacter(c));
  $("#deleteChar").addEventListener("click", () =>
    deleteEntity("character", c.name, `/api/characters/${c.id}`, () => go("characters")));
}

/* ---------------------------------------------------------------- Timeline */
async function viewTimeline(main) {
  main.innerHTML = head("Timeline Engine", "Timeline",
    "The universe in chronological order. Events carry connections — changing one shows what it touches.",
    `<button class="btn primary" id="addEvent">+ New event</button>`)
    + `<div id="timelineBody"></div>`;
  const { events, era_label } = await api(`/api/universes/${State.uid}/timeline`);
  $("#addEvent").addEventListener("click", () => openNewEvent(era_label));
  const body = $("#timelineBody");
  if (!events.length) { body.innerHTML = `<div class="empty-view"><div class="big">◷</div>No events yet.</div>`; return; }
  body.innerHTML = `<div class="timeline">${events.map(e => `
    <div class="tl-row">
      <div class="tl-year">${e.year != null ? esc(era_label) + " " + e.year : "—"}</div>
      <div class="tl-node"><span style="border-color:var(--${catColor(e.category)})"></span></div>
      <div class="tl-card">
        <button class="card-del" data-del-event="${e.id}" title="Delete">×</button>
        <div class="tl-t"><span class="cat-${esc(e.category)}">◆</span>${esc(e.title)}
          <span class="tag cat-${esc(e.category)}">${esc(e.category || "event")}</span></div>
        ${e.description ? `<div class="tl-d">${esc(e.description)}</div>` : ""}
        ${e.links.length ? `<div class="tl-links">${e.links.map(l =>
          `<span class="ref-chip">${esc(l.name)}</span>`).join("")}</div>` : ""}
      </div>
    </div>`).join("")}</div>`;
  $$("[data-del-event]", body).forEach(btn => btn.addEventListener("click", (e2) => {
    e2.stopPropagation();
    const ev = events.find(x => x.id === +btn.dataset.delEvent);
    deleteEntity("event", ev.title, `/api/events/${ev.id}`, () => go("timeline"));
  }));
}
function catColor(cat) {
  return { war: "err", death: "text-3", political: "character", discovery: "location", birth: "location" }[cat] || "accent";
}

/* --------------------------------------------------------------- Locations */
async function viewLocations(main) {
  main.innerHTML = head("Atlas", "Locations",
    "Countries, cities, stations, worlds — the places your story happens.") + `<div class="card-grid" id="locGrid"></div>`;
  const locs = await api(`/api/universes/${State.uid}/locations`);
  const grid = $("#locGrid");
  if (!locs.length) { grid.innerHTML = `<div class="empty-view" style="grid-column:1/-1"><div class="big">⌖</div>No locations yet.</div>`; return; }
  grid.innerHTML = locs.map(l => `
    <div class="card" data-loc="${l.id}">
      <div class="card-top"><div class="avatar t-location">⌖</div>
        <div><div class="nm">${esc(l.name)}</div><div class="role">${esc(l.kind || "Location")}</div></div></div>
      <div class="desc">${esc(l.description || "—")}</div>
      <div class="meta">${l.population ? `<span class="pill">Pop. ${esc(l.population)}</span>` : ""}</div>
    </div>`).join("");
  $$("[data-loc]", grid).forEach(el => el.addEventListener("click", () => {
    const l = locs.find(x => x.id === +el.dataset.loc);
    modal(`<div class="modal-head"><div class="avatar t-location">⌖</div>
      <div><h2>${esc(l.name)}</h2><div class="sub">${esc(l.kind)}</div></div><button class="modal-x" data-close>×</button></div>
      <div class="modal-body">
        ${l.population ? `<div class="field"><div class="lab">Population</div><div class="val">${esc(l.population)}</div></div>` : ""}
        <div class="field"><div class="lab">Description</div><div class="val">${esc(l.description || "—")}</div></div>
        ${l.history ? `<div class="field"><div class="lab">History</div><div class="val">${esc(l.history)}</div></div>` : ""}
        <div class="form-actions" style="margin-top:22px"><button class="btn danger" id="deleteLoc">Delete</button></div>
      </div>`);
    $("#deleteLoc").addEventListener("click", () =>
      deleteEntity("location", l.name, `/api/locations/${l.id}`, () => go("locations")));
  }));
}

/* ----------------------------------------------------------- Organizations */
async function viewOrganizations(main) {
  main.innerHTML = head("Structures", "Organizations",
    "Governments, militaries, factions, religions, companies — the powers that shape events.") + `<div class="card-grid" id="orgGrid"></div>`;
  const orgs = await api(`/api/universes/${State.uid}/organizations`);
  const grid = $("#orgGrid");
  if (!orgs.length) { grid.innerHTML = `<div class="empty-view" style="grid-column:1/-1"><div class="big">⬡</div>No organizations yet.</div>`; return; }
  grid.innerHTML = orgs.map(o => `
    <div class="card" data-org="${o.id}">
      <div class="card-top"><div class="avatar t-organization">⬡</div>
        <div><div class="nm">${esc(o.name)}</div><div class="role">${esc(o.kind || "Organization")}</div></div></div>
      <div class="desc">${esc(o.goals || o.history || "—")}</div>
      <div class="meta">${o.leader_name ? `<span class="pill">Led by ${esc(o.leader_name)}</span>` : `<span class="pill" style="color:var(--warn)">No leader</span>`}</div>
    </div>`).join("");
  $$("[data-org]", grid).forEach(el => el.addEventListener("click", () => {
    const o = orgs.find(x => x.id === +el.dataset.org);
    modal(`<div class="modal-head"><div class="avatar t-organization">⬡</div>
      <div><h2>${esc(o.name)}</h2><div class="sub">${esc(o.kind)}</div></div><button class="modal-x" data-close>×</button></div>
      <div class="modal-body">
        ${o.leader_name ? `<div class="field"><div class="lab">Leadership</div><div class="val">${esc(o.leader_name)}</div></div>` : ""}
        ${o.goals ? `<div class="field"><div class="lab">Goals</div><div class="val">${esc(o.goals)}</div></div>` : ""}
        ${o.history ? `<div class="field"><div class="lab">History</div><div class="val">${esc(o.history)}</div></div>` : ""}
        <div class="form-actions" style="margin-top:22px"><button class="btn danger" id="deleteOrg">Delete</button></div>
      </div>`);
    $("#deleteOrg").addEventListener("click", () =>
      deleteEntity("organization", o.name, `/api/organizations/${o.id}`, () => go("organizations")));
  }));
}

/* -------------------------------------------------------------------- Lore */
async function viewLore(main) {
  main.innerHTML = head("Lore System", "Lore",
    "Rules, culture, religion, technology, magic, language — the connective logic of the world.") + `<div id="loreBody"></div>`;
  const lore = await api(`/api/universes/${State.uid}/lore`);
  const body = $("#loreBody");
  if (!lore.length) { body.innerHTML = `<div class="empty-view"><div class="big">❋</div>No lore yet.</div>`; return; }
  const groups = {};
  lore.forEach(l => (groups[l.category || "General"] ||= []).push(l));
  body.innerHTML = Object.entries(groups).map(([cat, items]) => `
    <div class="lore-group"><h4>${esc(cat)}</h4>
      ${items.map(l => `<div class="lore-card" data-lore="${l.id}">
        <button class="card-del" data-del-lore="${l.id}" title="Delete">×</button>
        <div class="lt">${esc(l.title)}</div><div class="lc">${esc(l.content)}</div></div>`).join("")}
    </div>`).join("");
  $$("[data-del-lore]", body).forEach(btn => btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const l = lore.find(x => x.id === +btn.dataset.delLore);
    deleteEntity("lore entry", l.title, `/api/lore/${l.id}`, () => go("lore"));
  }));
}

/* ------------------------------------------------------------------ Scenes */
async function viewScenes(main) {
  main.innerHTML = head("Scene Database", "Scenes",
    "For writers and filmmakers: who's present, where, when, and what each scene is for.") + `<div id="sceneBody"></div>`;
  const scenes = await api(`/api/universes/${State.uid}/scenes`);
  const body = $("#sceneBody");
  if (!scenes.length) { body.innerHTML = `<div class="empty-view"><div class="big">▤</div>No scenes yet.</div>`; return; }
  body.innerHTML = scenes.map(s => `
    <div class="scene-card">
      <button class="card-del" data-del-scene="${s.id}" title="Delete">×</button>
      <div class="st">${esc(s.title)} ${s.time_year != null ? `<span class="tag">AE ${s.time_year}</span>` : ""}</div>
      <div class="sm">
        ${s.location_name ? `<span>⌖ ${esc(s.location_name)}</span>` : ""}
        ${s.purpose ? `<span>◆ ${esc(s.purpose)}</span>` : ""}
      </div>
      ${s.conflict ? `<div class="sd"><b style="color:var(--text)">Conflict:</b> ${esc(s.conflict)}</div>` : ""}
      ${s.info ? `<div class="sd" style="margin-top:6px;color:var(--text-3)">${esc(s.info)}</div>` : ""}
      ${s.characters.length ? `<div class="sc-chars">${s.characters.map(c =>
        `<span class="avatar t-character mini-avatar" data-character="${c.id}">${esc(c.name)}</span>`).join("")}</div>` : ""}
    </div>`).join("");
  $$("[data-character]", body).forEach(el => el.addEventListener("click", () => openCharacter(+el.dataset.character)));
  $$("[data-del-scene]", body).forEach(btn => btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const s = scenes.find(x => x.id === +btn.dataset.delScene);
    deleteEntity("scene", s.title, `/api/scenes/${s.id}`, () => go("scenes"));
  }));
}

/* ------------------------------------------------------------------- Graph */
async function viewGraph(main) {
  main.innerHTML = `<div class="page wide">${head("Universe Graph", "Relationship Graph",
    "Everything connects. Characters, locations, organizations, and events as one living web — drag to explore.")}
    <div class="graph-wrap" id="graphWrap">
      <div class="graph-legend">
        <div><span class="sw" style="background:var(--character)"></span>Character</div>
        <div><span class="sw" style="background:var(--location)"></span>Location</div>
        <div><span class="sw" style="background:var(--organization)"></span>Organization</div>
        <div><span class="sw" style="background:var(--event)"></span>Event</div>
      </div>
      <div class="graph-hint">Drag nodes · click a character to open it</div>
    </div></div>`;
  const data = await api(`/api/universes/${State.uid}/graph`);
  renderGraph($("#graphWrap"), data);
}

function renderGraph(wrap, data) {
  const W = wrap.clientWidth, H = wrap.clientHeight;
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  wrap.appendChild(svg);
  const gEdges = document.createElementNS(NS, "g");
  const gNodes = document.createElementNS(NS, "g");
  svg.appendChild(gEdges); svg.appendChild(gNodes);

  const colorOf = { character: "#7ea7ff", location: "#5cc9a0", organization: "#c07ad6", event: "#e08a5c" };
  const rOf = { character: 15, location: 13, organization: 13, event: 11 };

  // init positions on a circle + jitter
  const nodes = data.nodes.map((n, i) => {
    const a = (i / data.nodes.length) * Math.PI * 2;
    return { ...n, x: W / 2 + Math.cos(a) * Math.min(W, H) * 0.3 + (Math.random() - .5) * 40,
             y: H / 2 + Math.sin(a) * Math.min(W, H) * 0.3 + (Math.random() - .5) * 40, vx: 0, vy: 0 };
  });
  const byId = Object.fromEntries(nodes.map(n => [n.id, n]));
  const edges = data.edges.filter(e => byId[e.source] && byId[e.target])
    .map(e => ({ ...e, s: byId[e.source], t: byId[e.target] }));

  // draw edges
  const edgeEls = edges.map(e => {
    const line = document.createElementNS(NS, "line");
    line.setAttribute("class", "g-edge");
    gEdges.appendChild(line); e.el = line; return e;
  });
  // draw nodes
  nodes.forEach(n => {
    const g = document.createElementNS(NS, "g");
    g.setAttribute("class", "g-node");
    const c = document.createElementNS(NS, "circle");
    const r = rOf[n.type] || 12;
    c.setAttribute("r", r);
    c.setAttribute("fill", n.dead ? "#3a2530" : colorOf[n.type]);
    c.setAttribute("stroke", colorOf[n.type]);
    c.setAttribute("stroke-width", n.dead ? 2 : 0);
    c.setAttribute("opacity", n.dead ? .8 : 1);
    const t = document.createElementNS(NS, "text");
    t.setAttribute("text-anchor", "middle");
    t.setAttribute("dy", r + 13);
    t.textContent = n.label.length > 22 ? n.label.slice(0, 21) + "…" : n.label;
    g.appendChild(c); g.appendChild(t);
    gNodes.appendChild(g);
    n.el = g; n.r = r;
    g.addEventListener("mousedown", (ev) => startDrag(ev, n));
    g.addEventListener("click", () => { if (!n._moved && n.type === "character") openCharacter(+n.id.split("-")[1]); });
  });

  // force simulation (light Fruchterman-Reingold style)
  let ticks = 0;
  const sim = setInterval(() => {
    for (const a of nodes) {
      for (const b of nodes) {
        if (a === b) continue;
        let dx = a.x - b.x, dy = a.y - b.y, d2 = dx * dx + dy * dy || 1;
        const rep = 2600 / d2;
        a.vx += dx * rep * 0.02; a.vy += dy * rep * 0.02;
      }
    }
    for (const e of edgeEls) {
      let dx = e.t.x - e.s.x, dy = e.t.y - e.s.y, d = Math.hypot(dx, dy) || 1;
      const f = (d - 120) * 0.008;
      const fx = dx / d * f, fy = dy / d * f;
      if (!e.s.drag) { e.s.vx += fx; e.s.vy += fy; }
      if (!e.t.drag) { e.t.vx -= fx; e.t.vy -= fy; }
    }
    for (const n of nodes) {
      if (n.drag) continue;
      n.vx += (W / 2 - n.x) * 0.002; n.vy += (H / 2 - n.y) * 0.002;  // gentle centering
      n.vx *= 0.82; n.vy *= 0.82;
      n.x += n.vx; n.y += n.vy;
      n.x = Math.max(n.r + 6, Math.min(W - n.r - 6, n.x));
      n.y = Math.max(n.r + 6, Math.min(H - 20, n.y));
    }
    paint();
    if (++ticks > 300) clearInterval(sim);
  }, 16);

  function paint() {
    for (const e of edgeEls) {
      e.el.setAttribute("x1", e.s.x); e.el.setAttribute("y1", e.s.y);
      e.el.setAttribute("x2", e.t.x); e.el.setAttribute("y2", e.t.y);
    }
    for (const n of nodes) n.el.setAttribute("transform", `translate(${n.x},${n.y})`);
  }

  // dragging
  let dragging = null;
  function startDrag(ev, n) { ev.preventDefault(); dragging = n; n.drag = true; n._moved = false; }
  svg.addEventListener("mousemove", (ev) => {
    if (!dragging) return;
    const pt = svgPoint(ev);
    dragging.x = pt.x; dragging.y = pt.y; dragging.vx = dragging.vy = 0; dragging._moved = true;
    paint();
  });
  window.addEventListener("mouseup", () => { if (dragging) { dragging.drag = false; dragging = null; } });
  function svgPoint(ev) {
    const r = svg.getBoundingClientRect();
    return { x: (ev.clientX - r.left) / r.width * W, y: (ev.clientY - r.top) / r.height * H };
  }
}

/* --------------------------------------------------------------- Assistant */
function viewAssistant(main) {
  main.innerHTML = `<div class="page"><div class="ai-wrap">
    <div class="ai-hero">
      <div class="spark">✦</div>
      <h1 class="page-title" style="font-size:26px">AI Assistant</h1>
      <div class="page-sub" style="margin:0 auto">Ask the universe. Answers come from real queries over your
        graph — not invention. The assistant analyses; you stay in control.</div>
    </div>
    <div class="ai-input">
      <input id="aiInput" placeholder="e.g. Show every scene involving Mara">
      <button class="btn primary" id="aiAsk">Ask</button>
    </div>
    <div class="ai-suggest" id="aiSuggest">
      ${["Show every scene involving Mara", "Who has never met the Chancellor?",
         "What happens if Aldric dies?", "Who is connected to Torix?"]
        .map(s => `<button>${esc(s)}</button>`).join("")}
    </div>
    <div class="ai-log" id="aiLog"></div>
  </div></div>`;
  const input = $("#aiInput");
  const ask = async (q) => {
    q = (q || input.value).trim(); if (!q) return;
    input.value = "";
    const res = await api(`/api/universes/${State.uid}/ask`, { method: "POST", body: { q } });
    State.aiLog.unshift({ q, res });
    renderAiLog();
  };
  $("#aiAsk").addEventListener("click", () => ask());
  input.addEventListener("keydown", e => { if (e.key === "Enter") ask(); });
  $$("#aiSuggest button").forEach(b => b.addEventListener("click", () => ask(b.textContent)));
  renderAiLog();
  input.focus();
}
function renderAiLog() {
  const log = $("#aiLog"); if (!log) return;
  log.innerHTML = State.aiLog.map(({ q, res }) => {
    const items = res.items && res.items.length ? `<div class="result">${res.items.map(it => `
      <div class="result-row" ${it.type === "character" ? `data-character="${it.id}"` : ""} style="cursor:${it.type === "character" ? "pointer" : "default"}">
        <span class="rt">${esc(it.type)}</span><span class="rn">${esc(it.name)}</span>
        ${it.note ? `<span class="rnote">${esc(it.note)}</span>` : ""}</div>`).join("")}</div>`
      : `<div class="empty">No matching records — which is itself an answer.</div>`;
    return `<div class="ai-msg">
      <div class="ai-q"><span class="who">You</span><span>${esc(q)}</span></div>
      <div class="ai-a">
        <div class="headline">${esc(res.headline)}</div>
        ${res.explain ? `<div class="explain">${esc(res.explain)}</div>` : ""}
        ${res.intent === "unknown" ? "" : items}
      </div></div>`;
  }).join("");
  $$("[data-character]", log).forEach(el => el.addEventListener("click", () => openCharacter(+el.dataset.character)));
}

/* ------------------------------------------------------------- Canon Engine */
async function viewCanon(main) {
  main.innerHTML = head("Canon Engine · StoryDNA", "Consistency Audit",
    "The Canon Engine continuously checks your universe for contradictions. Every warning names the exact records in conflict.");
  const { warnings } = await api(`/api/universes/${State.uid}/canon`);
  const counts = warnings.reduce((a, w) => (a[w.severity] = (a[w.severity] || 0) + 1, a), {});
  const summary = `<div class="stat-grid" style="margin-bottom:22px">
    <div class="stat c-event"><div class="n" style="color:var(--err)">${counts.error || 0}</div><div class="l">Contradictions</div></div>
    <div class="stat c-character"><div class="n" style="color:var(--warn)">${counts.warning || 0}</div><div class="l">Warnings</div></div>
    <div class="stat c-location"><div class="n" style="color:var(--info)">${counts.info || 0}</div><div class="l">Suggestions</div></div>
  </div>`;
  const body = warnings.length
    ? summary + warnings.map(warnCard).join("")
    : `<div class="clean-state"><div class="big">✓</div><div style="font-size:16px;color:var(--text)">Canon is consistent.</div>
       <div style="margin-top:6px">No contradictions detected across characters, timeline, scenes, and relationships.</div></div>`;
  main.innerHTML = `<div class="page">${main.querySelector(".page-head").outerHTML}${body}</div>`;
  wireRefChips(main);
}

function warnCard(w) {
  const refs = (w.refs || []).map(r =>
    `<span class="ref-chip" data-ref-type="${r.type}" data-ref-id="${r.id}">${esc(r.type)} #${r.id}</span>`).join("");
  return `<div class="warn-card ${esc(w.severity)}">
    <span class="sev">${esc(w.severity)}</span>
    <div class="body"><div class="k">${esc(w.kind)}</div><div class="m">${esc(w.message)}</div>
      ${refs ? `<div class="refs">${refs}</div>` : ""}</div></div>`;
}
function wireRefChips(root) {
  $$("[data-ref-type]", root).forEach(el => el.addEventListener("click", () => {
    const t = el.dataset.refType;
    if (t === "character") openCharacter(+el.dataset.refId);
    else if (t === "scene") go("scenes");
    else if (t === "event") go("timeline");
    else if (t === "organization") go("organizations");
  }));
}

/* ------------------------------------------------------------------ Modals */
function modal(html) {
  $("#modalBody").innerHTML = html;
  $("#modalHost").classList.remove("hidden");
}
function closeModal() { $("#modalHost").classList.add("hidden"); }

async function deleteEntity(label, name, path, afterDelete) {
  if (!confirm(`Delete ${label} "${name}"? This cannot be undone.`)) return;
  await api(path, { method: "DELETE" });
  closeModal();
  await loadUniverse();
  await afterDelete();
}

function formModal(title, fieldsHtml, onSave, saveLabel = "Create", previewFn = null) {
  modal(`<div class="modal-head"><div><h2>${esc(title)}</h2></div><button class="modal-x" data-close>×</button></div>
    <div class="modal-body"><form id="modalForm">${fieldsHtml}
      <div id="previewPane"></div>
      <div class="form-actions"><button type="button" class="btn ghost" data-close>Cancel</button>
        ${previewFn ? `<button type="button" class="btn" id="previewBtn">Preview impact</button>` : ""}
        <button type="submit" class="btn primary">${esc(saveLabel)}</button></div></form></div>`);
  $$("[data-close]", $("#modalBody")).forEach(b => b.addEventListener("click", closeModal));
  $("#modalForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = {};
    $$("#modalForm [name]").forEach(el => data[el.name] = el.value);
    try { await onSave(data); } catch (err) { alert(err.message); }
  });
  if (previewFn) {
    $("#previewBtn").addEventListener("click", async () => {
      const data = {};
      $$("#modalForm [name]").forEach(el => data[el.name] = el.value);
      const pane = $("#previewPane");
      pane.innerHTML = `<div class="preview-loading">Checking impact…</div>`;
      try {
        const result = await previewFn(data);
        pane.innerHTML = renderPreviewResult(result);
        wireRefChips(pane);
      } catch (err) {
        pane.innerHTML = `<div class="preview-loading">Preview failed: ${esc(err.message)}</div>`;
      }
    });
  }
}
function renderPreviewResult(r) {
  if (!r.new_warnings.length && !r.resolved_warnings.length) {
    return `<div class="preview-pane clean">
      <div class="preview-head ok">✓ No change in canon impact</div>
      <div class="preview-sub">This edit introduces no new contradictions and resolves none of the existing ${r.before_count}.</div>
    </div>`;
  }
  const newBlock = r.new_warnings.length
    ? `<div class="preview-head warn">⚠ ${r.new_warnings.length} new contradiction${r.new_warnings.length === 1 ? "" : "s"} if you save this</div>
       ${r.new_warnings.map(warnCard).join("")}` : "";
  const resolvedBlock = r.resolved_warnings.length
    ? `<div class="preview-head ok">✓ ${r.resolved_warnings.length} resolved</div>
       ${r.resolved_warnings.map(warnCard).join("")}` : "";
  return `<div class="preview-pane">${newBlock}${resolvedBlock}</div>`;
}
const inp = (name, label, val = "", ph = "") =>
  `<div class="form-row"><label>${label}</label><input name="${name}" value="${esc(val)}" placeholder="${esc(ph)}"></div>`;
const txt = (name, label, val = "", ph = "") =>
  `<div class="form-row"><label>${label}</label><textarea name="${name}" placeholder="${esc(ph)}">${esc(val)}</textarea></div>`;

function openNewUniverse() {
  $("#universeMenu").classList.add("hidden");
  formModal("New Universe",
    inp("name", "Name", "", "My Film Universe")
    + inp("genre", "Genre", "", "Science fiction · Fantasy · Memoir · True crime · History…")
    + inp("era_label", "Calendar label", "Year", "Year, AE, AD…")
    + txt("summary", "Summary", "", "What is this world about?"),
    async (d) => {
      const u = await api("/api/universes", { method: "POST", body: d });
      State.universes.push(u); State.uid = u.id;
      renderUniverseSwitcher(); await loadUniverse(); closeModal(); go("dashboard");
    });
}

/* ------------------------------------------------------------- Draft import */
function openNewUniverseFromDraft() {
  $("#universeMenu").classList.add("hidden");
  formModal("New Universe from Draft",
    inp("name", "Name", "", "My Film Universe")
    + inp("genre", "Genre", "", "Science fiction · Fantasy · Memoir · True crime · History…")
    + inp("era_label", "Calendar label", "Year", "Year, AE, AD…"),
    async (d) => {
      const u = await api("/api/universes", { method: "POST", body: d });
      State.universes.push(u);
      renderUniverseSwitcher();
      openImportDraft(u.id, u.name);
    }, "Continue to draft");
}

function openPickUniverseForDraft() {
  $("#universeMenu").classList.add("hidden");
  if (!State.universes.length) { openNewUniverseFromDraft(); return; }
  const options = State.universes.map(u => `<option value="${u.id}">${esc(u.name)}</option>`).join("");
  modal(`<div class="modal-head"><div><h2>Add draft to existing universe</h2>
      <div class="sub">Choose which universe this draft belongs to — it's added to that universe's
        existing roster. Nothing elsewhere is touched.</div></div>
      <button class="modal-x" data-close>×</button></div>
    <div class="modal-body">
      <div class="form-row"><label>Universe</label><select id="pickUniverse">${options}</select></div>
      <div class="form-actions"><button type="button" class="btn ghost" data-close>Cancel</button>
        <button type="button" class="btn primary" id="pickContinue">Continue</button></div>
    </div>`);
  $$("[data-close]", $("#modalBody")).forEach(b => b.addEventListener("click", closeModal));
  $("#pickContinue").addEventListener("click", () => {
    const sel = $("#pickUniverse");
    openImportDraft(+sel.value, sel.options[sel.selectedIndex].textContent);
  });
}

function openImportDraft(targetUid, targetName, prefill = "") {
  modal(`
    <div class="modal-head"><div><h2>Import from draft</h2>
      <div class="sub">Importing into <b>${esc(targetName)}</b>. Paste what you've already written —
        chapters, notes, an outline. Story Atlas proposes the characters, places, factions, and scenes;
        nothing is saved until you say so.</div></div>
      <button class="modal-x" data-close>×</button></div>
    <div class="modal-body">
      <div class="form-row"><label>Draft text</label>
        <textarea id="draftText" style="min-height:240px" placeholder="Paste your draft here…">${esc(prefill)}</textarea></div>
      <div class="form-actions"><button type="button" class="btn ghost" data-close>Cancel</button>
        <button type="button" class="btn primary" id="analyzeDraft">Analyze</button></div>
    </div>`);
  $$("[data-close]", $("#modalBody")).forEach(b => b.addEventListener("click", closeModal));
  $("#draftText").focus();
  $("#analyzeDraft").addEventListener("click", async () => {
    const text = $("#draftText").value.trim();
    if (!text) return;
    const btn = $("#analyzeDraft");
    btn.disabled = true; btn.textContent = "Analyzing…";
    try {
      const preview = await api(`/api/universes/${targetUid}/draft/extract`, { method: "POST", body: { text } });
      renderDraftReview(targetUid, targetName, text, preview);
    } catch (err) {
      alert(err.message); btn.disabled = false; btn.textContent = "Analyze";
    }
  });
}

function renderDraftReview(targetUid, targetName, text, preview) {
  const checklist = (label, key, items) => `
    <div class="section-label">${esc(label)} (${items.length})</div>
    <div class="rel-list">${items.length ? items.map((it, i) => `
      <div class="rel-row draft-row" data-k="${key}" data-i="${i}">
        <input type="checkbox" class="draft-check" checked>
        <span>${esc(it.name)}</span>
        ${it.existing ? `<span class="pill" style="margin-left:auto">existing</span>` : ""}
      </div>`).join("") : `<div class="ai-a empty">Nothing detected — you can add these by hand afterward.</div>`}
    </div>`;
  const sceneRows = preview.scenes.length ? preview.scenes.map((s, i) => `
      <div class="rel-row draft-row" data-k="scenes" data-i="${i}">
        <input type="checkbox" class="draft-check" checked>
        <span>${esc(s.title)}${s.characters.length ? ` <small style="color:var(--text-3)">— ${s.characters.map(esc).join(", ")}</small>` : ""}</span>
      </div>`).join("") : `<div class="ai-a empty">No scene breaks detected — the whole draft reads as one scene.</div>`;
  const eventRows = preview.events.length ? preview.events.map((e, i) => `
      <div class="rel-row draft-row" data-k="events" data-i="${i}">
        <input type="checkbox" class="draft-check" checked>
        <span>${e.year != null ? `<b>${esc(e.year)}</b> — ` : ""}${esc(e.title)}${(e.characters || []).length
          ? ` <small style="color:var(--text-3)">— ${e.characters.map(esc).join(", ")}</small>` : ""}</span>
        <span class="pill" style="margin-left:auto">${esc(e.category)}</span>
      </div>`).join("") : `<div class="ai-a empty">No dated moments detected — add timeline events by hand once you're in.</div>`;
  const loreRows = preview.lore.length ? preview.lore.map((l, i) => `
      <div class="rel-row draft-row" data-k="lore" data-i="${i}">
        <input type="checkbox" class="draft-check" checked>
        <span>${esc(l.title)}</span>
        <span class="pill" style="margin-left:auto">${esc(l.category)}</span>
      </div>`).join("") : `<div class="ai-a empty">No world-building passages detected — add lore by hand once you're in.</div>`;

  const nerLine = preview.ner_available
    ? `<div class="tier-status ok">✓ Entity detection: heuristics + spaCy NER</div>`
    : `<div class="tier-status off">Entity detection: heuristics only — ${esc(preview.ner_note || "spaCy not installed")}</div>`;
  const corefLine = preview.coref_available
    ? `<div class="tier-status ok">✓ Coreference: pronouns resolved to named characters</div>`
    : `<div class="tier-status off">Coreference: unavailable — ${esc(preview.coref_note || "fastcoref not installed")}</div>`;
  const deepenNote = preview.deepen_note
    ? `<div class="tier-status ${preview.deepen_available === false ? "off" : "ok"}">${esc(preview.deepen_note)}</div>` : "";

  modal(`
    <div class="modal-head"><div><h2>Review the roster</h2>
      <div class="sub">Importing into <b>${esc(targetName)}</b>. Uncheck anything wrong. Renaming and filling
        in detail happens after import, same as any other character or location.</div></div>
      <button class="modal-x" data-close>×</button></div>
    <div class="modal-body">
      ${nerLine}${corefLine}${deepenNote}
      ${checklist("Characters", "characters", preview.characters)}
      ${checklist("Locations", "locations", preview.locations)}
      ${checklist("Organizations", "organizations", preview.organizations)}
      <div class="section-label">Scenes detected (${preview.scenes.length})</div>
      <div class="rel-list">${sceneRows}</div>
      <div class="section-label">Timeline events detected (${preview.events.length})</div>
      <div class="rel-list">${eventRows}</div>
      <div class="section-label">Lore detected (${preview.lore.length})</div>
      <div class="rel-list">${loreRows}</div>
      <div class="form-row"><label>Universe summary</label><textarea id="draftSummary">${esc(preview.summary)}</textarea></div>
      <div class="form-actions">
        <button type="button" class="btn ghost" id="backToDraft">‹ Back</button>
        <button type="button" class="btn ghost" id="deepenDraft">✦ Deepen with AI</button>
        <button type="button" class="btn primary" id="commitDraft">Import into universe</button>
      </div>
    </div>`);
  $$("[data-close]", $("#modalBody")).forEach(b => b.addEventListener("click", closeModal));
  $("#backToDraft").addEventListener("click", () => openImportDraft(targetUid, targetName, text));

  const included = (key, items) => items.filter((_, i) => {
    const row = $(`.draft-row[data-k="${key}"][data-i="${i}"]`);
    return row ? row.querySelector(".draft-check").checked : true;
  });

  $("#deepenDraft").addEventListener("click", async () => {
    const btn = $("#deepenDraft");
    btn.disabled = true; btn.textContent = "Reading the draft…";
    try {
      const body = {
        text,
        preview: {
          characters: preview.characters.map(c => c.name),
          locations: preview.locations.map(l => l.name),
          organizations: preview.organizations.map(o => o.name),
          events: preview.events,
          lore: preview.lore,
        },
      };
      const res = await api(`/api/universes/${targetUid}/draft/deepen`, { method: "POST", body });
      if (!res.available) {
        renderDraftReview(targetUid, targetName, text, { ...preview, deepen_available: false, deepen_note: res.note });
        return;
      }
      renderDraftReview(targetUid, targetName, text, {
        ...preview,
        characters: res.characters, locations: res.locations, organizations: res.organizations,
        events: res.events, lore: res.lore,
        deepen_available: true, deepen_note: res.note || "Deepened with AI.",
      });
    } catch (err) {
      renderDraftReview(targetUid, targetName, text, { ...preview, deepen_available: false, deepen_note: err.message });
    }
  });

  $("#commitDraft").addEventListener("click", async () => {
    const btn = $("#commitDraft");
    btn.disabled = true; btn.textContent = "Importing…";
    try {
      const body = {
        text,
        summary: $("#draftSummary").value,
        characters: included("characters", preview.characters).map(c => c.name),
        locations: included("locations", preview.locations).map(l => l.name),
        organizations: included("organizations", preview.organizations).map(o => o.name),
        scenes: included("scenes", preview.scenes),
        events: included("events", preview.events),
        lore: included("lore", preview.lore),
        character_relations: preview.character_relations || [],
      };
      await api(`/api/universes/${targetUid}/draft/commit`, { method: "POST", body });
      closeModal();
      State.uid = targetUid;
      renderUniverseSwitcher();
      await loadUniverse();
      go("dashboard");
    } catch (err) {
      alert(err.message); btn.disabled = false; btn.textContent = "Import into universe";
    }
  });
}

function openNewCharacter() {
  formModal("New Character",
    `<div class="form-grid">${inp("name", "Name")}${inp("role", "Role / title")}</div>
     <div class="form-grid">${inp("age", "Age")}
       <div class="form-row"><label>Status</label><select name="status">
         <option value="alive">Alive</option><option value="dead">Deceased</option><option value="unknown">Unknown</option></select></div></div>
     <div class="form-grid">${inp("birth_year", "Birth year")}${inp("death_year", "Death year")}</div>
     ${txt("biography", "Biography")}${txt("personality", "Personality")}
     <div class="form-grid">${txt("goals", "Goals")}${txt("motivations", "Motivations")}</div>
     <div class="form-grid">${txt("fears", "Fears")}${txt("conflicts", "Conflicts")}</div>
     ${txt("arc", "Character arc")}`,
    async (d) => {
      await api(`/api/universes/${State.uid}/characters`, { method: "POST", body: d });
      closeModal(); await loadUniverse(); go("characters");
    });
}

function openEditCharacter(c) {
  formModal(`Edit ${c.name}`,
    `<div class="form-grid">${inp("name", "Name", c.name)}${inp("role", "Role / title", c.role)}</div>
     <div class="form-grid">${inp("age", "Age", c.age)}
       <div class="form-row"><label>Status</label><select name="status">
         ${["alive", "dead", "unknown"].map(s => `<option value="${s}" ${c.status === s ? "selected" : ""}>${s}</option>`).join("")}
       </select></div></div>
     <div class="form-grid">${inp("birth_year", "Birth year", c.birth_year ?? "")}${inp("death_year", "Death year", c.death_year ?? "")}</div>
     ${txt("biography", "Biography", c.biography)}${txt("personality", "Personality", c.personality)}
     <div class="form-grid">${txt("goals", "Goals", c.goals)}${txt("motivations", "Motivations", c.motivations)}</div>
     <div class="form-grid">${txt("fears", "Fears", c.fears)}${txt("conflicts", "Conflicts", c.conflicts)}</div>
     ${txt("arc", "Character arc", c.arc)}`,
    async (d) => {
      await api(`/api/characters/${c.id}`, { method: "PUT", body: d });
      closeModal(); await loadUniverse(); go("characters");
    }, "Save changes",
    (d) => api(`/api/characters/${c.id}/canon-preview`, { method: "POST", body: d }));
}

function openNewEvent(era) {
  formModal("New Timeline Event",
    `<div class="form-grid">${inp("title", "Title")}${inp("year", `Year (${era})`)}</div>
     <div class="form-row"><label>Category</label><select name="category">
       ${["political", "war", "death", "birth", "discovery", "character"].map(c => `<option value="${c}">${c}</option>`).join("")}
     </select></div>
     ${txt("description", "Description")}`,
    async (d) => {
      await api(`/api/universes/${State.uid}/events`, { method: "POST", body: d });
      closeModal(); await loadUniverse(); go("timeline");
    });
}

boot().catch(e => { $("#main").innerHTML = `<div class="page">Failed to load: ${esc(e.message)}</div>`; });

/* ---- command palette (Ctrl/Cmd+K) — searches /api/universes/:uid/search
   live, scoped to the open universe. Read-only, additive endpoint. -------- */
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
      host.innerHTML = '<div class="palette-empty">Type to search this universe…</div>';
      return;
    }
    host.innerHTML = list.map((r, i) =>
      `<div class="palette-row${i === 0 ? " sel" : ""}" data-i="${i}">
         <span class="palette-type">${r.type}</span>
         <span class="palette-title">${esc(r.title)}</span>
         <span class="palette-sub">${esc(r.subtitle || "")}</span>
       </div>`
    ).join("");
    $$(".palette-row", host).forEach((el, i) => el.addEventListener("click", () => selectResult(i)));
  }

  function selectResult(i) {
    const r = results[i];
    if (!r) return;
    closePalette();
    go(r.view);
    if (r.type === "Character") setTimeout(() => openCharacter(r.id), 0);
  }

  function highlight() {
    const { list: host } = els();
    if (!host) return;
    $$(".palette-row", host).forEach((el, i) => el.classList.toggle("sel", i === selIdx));
  }

  async function runSearch(q) {
    if (!q.trim() || !State.uid) { renderResults([]); return; }
    try {
      const data = await api(`/api/universes/${State.uid}/search?q=${encodeURIComponent(q)}`);
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
      else if (e.key === "Enter") { e.preventDefault(); selectResult(selIdx); }
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
