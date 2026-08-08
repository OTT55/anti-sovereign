"""
Story Atlas — the creative intelligence workspace.

Seeds the Sovereign Stack company **Story Atlas**: a structured operating
environment for building, organizing, and maintaining any story — a novel, a
screenplay, a memoir, a true-crime investigation, a biography, a game, a
history — fiction or not. Notion + Obsidian + a studio production bible + a
reasoning engine.

A universe is not a pile of notes. It is a connected system: characters,
locations, organizations, timeline events, scenes, and lore, all wired to each
other by typed relationships. Two subsystems make that graph *intelligent*, and
both are real logic over the data — nothing here is faked:

  • The **Canon Engine** (the "StoryDNA" concept) continuously audits the
    universe for consistency: a character present in a scene set after their
    death, an event that references someone who was not yet born, a relationship
    pointing at an entity that no longer exists, a leaderless organization, an
    orphaned character. Every warning names the exact records in conflict.

  • The **AI Assistant** answers structured questions by *querying the graph*,
    not by guessing: "show every scene involving this character", "who has never
    met the ruler", "what changes if this character dies". The intent parser
    maps natural questions onto real traversals and returns cited results.

Stack: Flask + SQLite + hand-written HTML/CSS/JS. Dark, editorial, premium.

Run:  python app.py   →  http://127.0.0.1:5109
"""

import json
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import Flask, g, jsonify, redirect, render_template, request, session, url_for

BASE_DIR = Path(__file__).parent


def _load_env_file(path):
    """A single-file, dependency-free KEY=VALUE loader — not a new pip
    package for one file. setdefault, not assignment: an already-exported
    real environment variable always wins over this convenience file."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    except FileNotFoundError:
        pass


# The CreativeOS-wide API key lives one level up, shared across sibling
# products rather than duplicated per-app — see companies/creativeos/.env.txt
# (gitignored; never commit it).
_load_env_file(BASE_DIR / ".." / ".env.txt")

DB_PATH = os.environ.get("STORY_ATLAS_DB", str(BASE_DIR / "story_atlas.db"))
PORT = int(os.environ.get("STORY_ATLAS_PORT", "5109"))
DEBUG = os.environ.get("STORY_ATLAS_DEBUG", "0") == "1"
CLAUDE_MODEL = "claude-opus-5"

# Identity + credit seams to FrameVault — same pattern as every other
# CreativeOS product (FilmCrew, RightsForge, CreatorStack, OTT Studio):
#   1. IDENTITY — /api/authenticate: one login across CreativeOS.
#   2. CREDIT   — /api/credit: publishing a universe writes `canon.published`
#      onto the creator's FrameVault.
FRAMEVAULT_URL = os.environ.get("FRAMEVAULT_URL", "http://127.0.0.1:5001")
SERVICE_KEY = os.environ.get("FV_SERVICE_KEY", "creativeos-dev-service-key")

app = Flask(__name__)
app.secret_key = os.environ.get("SA_SECRET", "story-atlas-dev-secret-change-in-production")


# --------------------------------------------------------------------------- #
#  Database                                                                    #
# --------------------------------------------------------------------------- #
def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS universes (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  name        TEXT NOT NULL,
  genre       TEXT NOT NULL DEFAULT '',
  summary     TEXT NOT NULL DEFAULT '',
  era_label   TEXT NOT NULL DEFAULT 'Year',
  created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS characters (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  universe_id  INTEGER NOT NULL REFERENCES universes(id) ON DELETE CASCADE,
  name         TEXT NOT NULL,
  role         TEXT NOT NULL DEFAULT '',
  age          TEXT NOT NULL DEFAULT '',
  appearance   TEXT NOT NULL DEFAULT '',
  biography    TEXT NOT NULL DEFAULT '',
  personality  TEXT NOT NULL DEFAULT '',
  goals        TEXT NOT NULL DEFAULT '',
  motivations  TEXT NOT NULL DEFAULT '',
  fears        TEXT NOT NULL DEFAULT '',
  conflicts    TEXT NOT NULL DEFAULT '',
  arc          TEXT NOT NULL DEFAULT '',
  status       TEXT NOT NULL DEFAULT 'alive',   -- alive | dead | unknown
  birth_year   INTEGER,
  death_year   INTEGER,
  created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS locations (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  universe_id  INTEGER NOT NULL REFERENCES universes(id) ON DELETE CASCADE,
  name         TEXT NOT NULL,
  kind         TEXT NOT NULL DEFAULT '',
  description  TEXT NOT NULL DEFAULT '',
  history      TEXT NOT NULL DEFAULT '',
  population   TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS organizations (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  universe_id  INTEGER NOT NULL REFERENCES universes(id) ON DELETE CASCADE,
  name         TEXT NOT NULL,
  kind         TEXT NOT NULL DEFAULT '',
  leadership   TEXT NOT NULL DEFAULT '',    -- character id (as text) or free name
  goals        TEXT NOT NULL DEFAULT '',
  history      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS events (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  universe_id  INTEGER NOT NULL REFERENCES universes(id) ON DELETE CASCADE,
  title        TEXT NOT NULL,
  year         INTEGER,
  category     TEXT NOT NULL DEFAULT '',     -- war | death | birth | discovery | political | character
  description  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS scenes (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  universe_id  INTEGER NOT NULL REFERENCES universes(id) ON DELETE CASCADE,
  title        TEXT NOT NULL,
  location_id  INTEGER REFERENCES locations(id) ON DELETE SET NULL,
  time_year    INTEGER,
  purpose      TEXT NOT NULL DEFAULT '',
  conflict     TEXT NOT NULL DEFAULT '',
  info         TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS lore (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  universe_id  INTEGER NOT NULL REFERENCES universes(id) ON DELETE CASCADE,
  title        TEXT NOT NULL,
  category     TEXT NOT NULL DEFAULT '',
  content      TEXT NOT NULL DEFAULT ''
);

-- Typed edges between any two entities. (source_type, source_id) -> (target_type, target_id)
CREATE TABLE IF NOT EXISTS relationships (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  universe_id  INTEGER NOT NULL REFERENCES universes(id) ON DELETE CASCADE,
  source_type  TEXT NOT NULL,   -- character | location | organization | event
  source_id    INTEGER NOT NULL,
  target_type  TEXT NOT NULL,
  target_id    INTEGER NOT NULL,
  kind         TEXT NOT NULL DEFAULT 'linked',  -- family|ally|enemy|romance|member|located|caused|...
  label        TEXT NOT NULL DEFAULT ''
);

-- Which characters appear in which scene.
CREATE TABLE IF NOT EXISTS scene_characters (
  scene_id     INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
  character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  PRIMARY KEY (scene_id, character_id)
);

-- A pasted draft, kept for provenance so re-importing can extend the roster
-- instead of duplicating it.
CREATE TABLE IF NOT EXISTS drafts (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  universe_id  INTEGER NOT NULL REFERENCES universes(id) ON DELETE CASCADE,
  content      TEXT NOT NULL DEFAULT '',
  summary      TEXT NOT NULL DEFAULT '',
  created_at   TEXT NOT NULL
);
"""


def _migrate(con):
    """CREATE TABLE IF NOT EXISTS doesn't add columns to a table that already
    exists from an older version of SCHEMA — published_at postdates the
    original universes table. Add it if missing."""
    cols = {row[1] for row in con.execute("PRAGMA table_info(universes)")}
    if "published_at" not in cols:
        con.execute("ALTER TABLE universes ADD COLUMN published_at TEXT")
    if "published_by" not in cols:
        con.execute("ALTER TABLE universes ADD COLUMN published_by TEXT")


def init_db():
    fresh = not Path(DB_PATH).exists()
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    _migrate(con)
    con.commit()
    # Seed only when the universe table is empty, so restarts keep user edits.
    if con.execute("SELECT COUNT(*) AS n FROM universes").fetchone()["n"] == 0:
        seed(con)
    con.close()
    if fresh:
        print(f"  Story Atlas — initialised database at {DB_PATH}")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- #
#  Seed data — a self-consistent demo universe, plus two deliberate canon
#  violations so the Canon Engine has something real to catch on first run.
# --------------------------------------------------------------------------- #
def seed(con: sqlite3.Connection):
    ts = now()
    uid = con.execute(
        "INSERT INTO universes(name, genre, summary, era_label, created_at) VALUES(?,?,?,?,?)",
        (
            "Meridian",
            "Political science fiction",
            "Two centuries after Earth seeded the Meridian system, three colony "
            "worlds fracture over who controls the jump-gate that connects them. "
            "A study of power, inheritance, and the cost of keeping a fragile peace.",
            "AE",  # After Expansion
            ts,
        ),
    ).lastrowid

    def ch(**k):
        cols = ("name role age appearance biography personality goals motivations "
                "fears conflicts arc status birth_year death_year").split()
        vals = [k.get(c, None if c in ("birth_year", "death_year") else "") for c in cols]
        return con.execute(
            f"INSERT INTO characters(universe_id,{','.join(cols)},created_at) "
            f"VALUES(?,{','.join('?'*len(cols))},?)",
            (uid, *vals, ts),
        ).lastrowid

    kestrel = ch(
        name="Chancellor Aldric Vane", role="Ruler of the Meridian Compact",
        age="61", appearance="Silver-haired, deliberate, always in Compact grey.",
        biography="Rose from the Ardenne shipyards to broker the Treaty of Halden "
                  "that ended the First Gate War. Has held the Chancellery for 19 years.",
        personality="Patient, calculating, allergic to spectacle.",
        goals="Keep the three worlds inside one Compact until the succession is secure.",
        motivations="Believes only a unified Meridian survives contact with Earth.",
        fears="That his death reopens the war he spent his life closing.",
        conflicts="His chosen heir is not his blood; his blood wants the seat.",
        arc="From indispensable peacemaker to a man who learns the peace outlived his usefulness.",
        status="alive", birth_year=239,
    )
    mara = ch(
        name="Mara Vane", role="Envoy of Ardenne",
        age="34", appearance="Sharp, close-cropped hair, a diplomat's stillness.",
        biography="Aldric's adopted daughter, raised in the Chancellery, trained as "
                  "the Compact's youngest envoy. Negotiated the Ceres water accords at 29.",
        personality="Principled, stubborn, better at reading rooms than her father admits.",
        goals="Prove an heir can be chosen on merit, not blood.",
        motivations="Owes everything to a man who chose her; wants to deserve it.",
        fears="That she is only ever the compromise candidate.",
        conflicts="Torix, Aldric's nephew, considers the Chancellery his by right.",
        arc="From loyal instrument to independent power who must decide whether to keep the Compact whole.",
        status="alive", birth_year=266,
    )
    torix = ch(
        name="Torix Vane", role="Prefect of Halden Station",
        age="41", appearance="Broad, restless, wears military cut even in council.",
        biography="Aldric's nephew and the Compact's fleet prefect. Commands the "
                  "guns that hold the jump-gate.",
        personality="Charismatic, aggrieved, genuinely capable.",
        goals="Take the Chancellery he believes was stolen from his line.",
        motivations="Raised to expect the seat; watched an outsider be groomed for it instead.",
        fears="Being remembered as the usurper rather than the rightful heir.",
        conflicts="Mara. The Compact's own succession law, which he reads differently than she does.",
        arc="From loyal enforcer to open rival — the story's engine of crisis.",
        status="alive", birth_year=259,
    )
    sela = ch(
        name="Dr. Sela Ondt", role="Gate Engineer, Free Ceres",
        age="47", appearance="Weathered, ink-stained cuffs, jump-math in her margins.",
        biography="The only living engineer who understands the Halden gate's failing "
                  "core. Ceres-born, no love for the Compact that taxes her world.",
        personality="Dry, exacting, quietly radical.",
        goals="Free Ceres from Compact control of the gate.",
        motivations="Watched Ceres bleed to fund a peace it never voted for.",
        fears="That the gate fails before anyone is ready — and takes Ceres with it.",
        conflicts="The Compact needs her; she needs the Compact gone.",
        arc="From reluctant contractor to the person who holds everyone's fate in a maintenance log.",
        status="alive", birth_year=253,
    )
    halden_founder = ch(
        name="Admiral Josa Halden", role="Founder of the Compact (historical)",
        age="—", appearance="Known only from the statue on Halden Station.",
        biography="Ended the First Gate War and died the year the Compact was signed. "
                  "Every institution in the system carries her name.",
        personality="Remembered as ruthless and far-sighted in equal measure.",
        goals="A single lawful authority over the gate.",
        motivations="Had seen what an ungoverned gate did to the first colonists.",
        fears="—",
        conflicts="—",
        arc="Dead before the story opens; her succession law is what everyone now fights over.",
        status="dead", birth_year=180, death_year=241,
    )

    # Locations
    def loc(**k):
        cols = "name kind description history population".split()
        return con.execute(
            f"INSERT INTO locations(universe_id,{','.join(cols)}) VALUES(?,{','.join('?'*len(cols))})",
            (uid, *[k.get(c, "") for c in cols]),
        ).lastrowid

    halden = loc(name="Halden Station", kind="Orbital station",
                 description="The fortified ring around the Meridian jump-gate; seat of the Compact fleet.",
                 history="Built on the wreck of the war fleet that took the gate in AE 241.",
                 population="~120,000")
    ardenne = loc(name="Ardenne", kind="Colony world",
                  description="The Compact's industrial heart and Aldric's homeworld.",
                  history="First world settled after Expansion; oldest shipyards in the system.",
                  population="410 million")
    ceres = loc(name="Free Ceres", kind="Colony world",
                description="Water-rich outer world, taxed by the Compact, restless for independence.",
                history="Settled last, governed least, resents most.",
                population="88 million")

    # Organizations
    def org(**k):
        cols = "name kind leadership goals history".split()
        return con.execute(
            f"INSERT INTO organizations(universe_id,{','.join(cols)}) VALUES(?,{','.join('?'*len(cols))})",
            (uid, *[k.get(c, "") for c in cols]),
        ).lastrowid

    compact = org(name="The Meridian Compact", kind="Government",
                  leadership=str(kestrel), goals="Hold the three worlds under one lawful authority.",
                  history="Founded AE 241 under Halden's succession law.")
    fleet = org(name="Compact Gate Fleet", kind="Military",
                leadership=str(torix), goals="Control of the jump-gate at Halden.",
                history="Descended from Halden's war fleet.")
    freeceres = org(name="Free Ceres Movement", kind="Faction",
                    leadership=str(sela), goals="Independence from Compact gate control.",
                    history="Grew from the Ceres tax revolts of the 280s.")

    # Timeline events
    def ev(**k):
        cols = "title year category description".split()
        return con.execute(
            f"INSERT INTO events(universe_id,{','.join(cols)}) VALUES(?,{','.join('?'*len(cols))})",
            (uid, *[k.get(c, "") for c in cols]),
        ).lastrowid

    e_war = ev(title="First Gate War ends", year=241, category="war",
               description="Halden takes the gate; the Compact is signed.")
    e_hd = ev(title="Death of Admiral Halden", year=241, category="death",
              description="Dies the year the Compact is founded; her succession law survives her.")
    e_ch = ev(title="Aldric Vane becomes Chancellor", year=287, category="political",
              description="Ends a decade of unstable Chancellors after the Halden line dies out.")
    e_ceres = ev(title="Ceres water accords", year=295, category="political",
                 description="Mara negotiates a tax truce; the Free Ceres Movement calls it a sellout.")
    e_core = ev(title="Halden gate core begins failing", year=299, category="discovery",
                description="Dr. Ondt's survey finds the core will not hold another decade.")

    # Scenes
    def scene(location_id=None, chars=(), **k):
        cols = "title location_id time_year purpose conflict info".split()
        sid = con.execute(
            f"INSERT INTO scenes(universe_id,{','.join(cols)}) VALUES(?,{','.join('?'*len(cols))})",
            (uid, k.get("title", ""), location_id, k.get("time_year"),
             k.get("purpose", ""), k.get("conflict", ""), k.get("info", "")),
        ).lastrowid
        for cid in chars:
            con.execute("INSERT INTO scene_characters(scene_id, character_id) VALUES(?,?)", (sid, cid))
        return sid

    scene(title="The Succession Council", location_id=halden, time_year=299,
          chars=[kestrel, mara, torix],
          purpose="Aldric names Mara his heir before the council.",
          conflict="Torix challenges the naming as a breach of Halden's law.",
          info="Establishes the central power struggle.")
    scene(title="The Maintenance Log", location_id=ceres, time_year=299,
          chars=[sela, mara],
          purpose="Sela reveals the gate core is dying; Mara realizes the peace has a deadline.",
          conflict="Sela wants Ceres free before she fixes it; Mara needs it fixed to hold the Compact.",
          info="Ties the personal succession plot to the system-wide stakes.")
    scene(title="Prefect's Gambit", location_id=halden, time_year=300,
          chars=[torix, sela],
          purpose="Torix offers Ceres a seat if Sela's fleet backs his claim.",
          conflict="An alliance of convenience between two people who despise the Compact.",
          info="Turns rivalry into open crisis.")

    # Lore
    def lore(**k):
        cols = "title category content".split()
        con.execute(
            f"INSERT INTO lore(universe_id,{','.join(cols)}) VALUES(?,{','.join('?'*len(cols))})",
            (uid, *[k.get(c, "") for c in cols]),
        )

    lore(title="Halden's Succession Law", category="Law/Politics",
         content="The Chancellery passes to the most fit successor named by the sitting "
                 "Chancellor — not by blood. Torix reads 'fit' as 'of the founding line'; "
                 "Mara reads it as 'chosen on merit'. The whole conflict lives in one word.")
    lore(title="The Jump-Gate", category="Technology",
         content="A single fixed gate at Halden connects Meridian to Earth's lanes. Whoever "
                 "holds Halden holds the economy of three worlds. Its core is not eternal.")
    lore(title="After Expansion (AE) calendar", category="Culture",
         content="Years are counted from the Expansion fleet's arrival. The story opens in AE 300.")

    # Relationships (the graph)
    def rel(st, sid, tt, tid, kind, label=""):
        con.execute(
            "INSERT INTO relationships(universe_id,source_type,source_id,target_type,target_id,kind,label) "
            "VALUES(?,?,?,?,?,?,?)", (uid, st, sid, tt, tid, kind, label))

    rel("character", mara, "character", kestrel, "family", "adopted daughter")
    rel("character", torix, "character", kestrel, "family", "nephew")
    rel("character", torix, "character", mara, "enemy", "rival heir")
    rel("character", sela, "character", torix, "ally", "alliance of convenience")
    rel("character", mara, "character", sela, "ally", "uneasy")
    rel("character", kestrel, "organization", compact, "member", "Chancellor")
    rel("character", torix, "organization", fleet, "member", "Prefect")
    rel("character", sela, "organization", freeceres, "member", "leader")
    rel("character", sela, "location", ceres, "located", "home")
    rel("character", kestrel, "location", ardenne, "located", "homeworld")
    rel("organization", fleet, "location", halden, "located", "based at")
    rel("organization", compact, "location", halden, "located", "seat")
    rel("event", e_ch, "character", kestrel, "caused", "became Chancellor")
    rel("event", e_core, "character", sela, "caused", "discovered by")
    rel("event", e_ceres, "character", mara, "caused", "negotiated by")

    # ---- Two DELIBERATE canon violations so the engine has real catches ----
    # 1) A scene set in AE 245 that includes Mara (born 266) — she does not exist yet.
    scene(title="[demo flaw] The Old Accord", location_id=ardenne, time_year=245,
          chars=[mara],
          purpose="Placeholder scene left in from an earlier draft.",
          conflict="—",
          info="Intentionally inconsistent: Mara is not born until AE 266.")
    # 2) An event in AE 250 that references Admiral Josa Halden, who died in AE 241.
    e_flaw = ev(title="[demo flaw] Josa Halden addresses the council", year=250, category="political",
                description="Records Admiral Josa Halden speaking in AE 250 — nine years after her death.")
    rel("event", e_flaw, "character", halden_founder, "caused", "references")
    # Wire the historical admiral into the founding war so she is not merely orphaned.
    rel("event", e_hd, "character", halden_founder, "caused", "death of")
    rel("event", e_war, "character", halden_founder, "caused", "won by")

    con.commit()


# --------------------------------------------------------------------------- #
#  Serialization helpers                                                       #
# --------------------------------------------------------------------------- #
def rows(sql, args=()):
    return [dict(r) for r in get_db().execute(sql, args).fetchall()]


def one(sql, args=()):
    r = get_db().execute(sql, args).fetchone()
    return dict(r) if r else None


ENTITY_TABLE = {
    "character": "characters",
    "location": "locations",
    "organization": "organizations",
    "event": "events",
    "scene": "scenes",
}
ENTITY_NAME_COL = {
    "character": "name", "location": "name", "organization": "name",
    "event": "title", "scene": "title",
}


def entity_label(etype, eid):
    tbl = ENTITY_TABLE.get(etype)
    if not tbl:
        return f"{etype}#{eid}"
    col = ENTITY_NAME_COL[etype]
    r = one(f"SELECT {col} AS label FROM {tbl} WHERE id=?", (eid,))
    return r["label"] if r else f"{etype}#{eid} (missing)"


# --------------------------------------------------------------------------- #
#  Genre adaptation — a universe's genre changes which canon checks matter.
#  A leaderless faction is a real gap in a political epic; it's noise in a
#  slice-of-life romance. The bucket below tunes severity, not correctness —
#  every check still only fires on real graph state.
# --------------------------------------------------------------------------- #
GENRE_BUCKETS = {
    "political": ("political", "war", "military", "dystopia", "space opera",
                  "science fiction", "sci-fi", "empire", "historical"),
    "fantasy": ("fantasy", "magic", "myth", "sword", "epic"),
    "romance": ("romance", "romantic",),
    "mystery": ("mystery", "thriller", "crime", "detective", "noir", "suspense", "heist"),
    "horror": ("horror", "gothic", "supernatural"),
}


def genre_bucket(genre_text):
    g = (genre_text or "").lower()
    for bucket, keys in GENRE_BUCKETS.items():
        if any(k in g for k in keys):
            return bucket
    return "general"


TITLES = {"admiral", "chancellor", "dr", "dr.", "prefect", "envoy", "mr", "mrs",
          "ms", "sir", "lady", "lord", "king", "queen", "captain", "general"}


def _distinctive_tokens(name):
    return [t for t in name.lower().split() if t not in TITLES and len(t) > 3]


# --------------------------------------------------------------------------- #
#  Canon Engine — real consistency auditing over the universe graph.
#  Every warning names the exact records in conflict.
# --------------------------------------------------------------------------- #
def canon_check(uid: int):
    def as_year(v):
        """Coerce any stored value to an int year or None — defensive against blanks."""
        if v is None or (isinstance(v, str) and not v.strip().lstrip("-").isdigit()):
            return None
        return int(v)

    u = one("SELECT genre FROM universes WHERE id=?", (uid,))
    bucket = genre_bucket(u["genre"] if u else "")
    warnings = []
    chars = {c["id"]: c for c in rows("SELECT * FROM characters WHERE universe_id=?", (uid,))}
    for c in chars.values():
        c["birth_year"] = as_year(c["birth_year"])
        c["death_year"] = as_year(c["death_year"])
    events = rows("SELECT * FROM events WHERE universe_id=?", (uid,))
    scenes = rows("SELECT * FROM scenes WHERE universe_id=?", (uid,))
    rels = rows("SELECT * FROM relationships WHERE universe_id=?", (uid,))
    orgs = rows("SELECT * FROM organizations WHERE universe_id=?", (uid,))

    def w(severity, kind, message, refs):
        warnings.append({"severity": severity, "kind": kind, "message": message, "refs": refs})

    # 1) Life-span sanity: death before birth.
    for c in chars.values():
        if c["birth_year"] is not None and c["death_year"] is not None and c["death_year"] < c["birth_year"]:
            w("error", "Impossible lifespan",
              f"{c['name']} dies in {c['death_year']} but is born in {c['birth_year']}.",
              [{"type": "character", "id": c["id"]}])

    # 2) A character present in a scene set before their birth or after their death.
    sc_map = {}
    for r in rows("SELECT * FROM scene_characters", ()):
        sc_map.setdefault(r["scene_id"], []).append(r["character_id"])
    for s in scenes:
        ty = s["time_year"]
        if ty is None:
            continue
        for cid in sc_map.get(s["id"], []):
            c = chars.get(cid)
            if not c:
                continue
            if c["birth_year"] is not None and ty < c["birth_year"]:
                w("error", "Timeline contradiction",
                  f"“{s['title']}” is set in {ty}, but {c['name']} is not born until {c['birth_year']}.",
                  [{"type": "scene", "id": s["id"]}, {"type": "character", "id": c["id"]}])
            if c["death_year"] is not None and ty > c["death_year"]:
                w("error", "Timeline contradiction",
                  f"“{s['title']}” is set in {ty}, but {c['name']} died in {c['death_year']}.",
                  [{"type": "scene", "id": s["id"]}, {"type": "character", "id": c["id"]}])

    # 3) An event that names a dead character but is dated after their death.
    #    Match on the character's *distinctive* name tokens (title words and very
    #    short tokens dropped), and require them all to appear — so a surname that
    #    also names a place or dynasty ("Halden Station") does not false-positive.
    for e in events:
        if e["year"] is None:
            continue
        text = f"{e['title']} {e['description']}".lower()
        for c in chars.values():
            if c["death_year"] is None or e["year"] <= c["death_year"]:
                continue
            tokens = _distinctive_tokens(c["name"])
            if tokens and all(t in text for t in tokens):
                w("warning", "Posthumous reference",
                  f"Event “{e['title']}” ({e['year']}) references {c['name']}, "
                  f"who died in {c['death_year']}.",
                  [{"type": "event", "id": e["id"]}, {"type": "character", "id": c["id"]}])

    # 4) Dangling relationships: an edge whose endpoint no longer exists.
    for r in rels:
        for side in ("source", "target"):
            et, eid = r[f"{side}_type"], r[f"{side}_id"]
            tbl = ENTITY_TABLE.get(et)
            if tbl and not one(f"SELECT 1 FROM {tbl} WHERE id=?", (eid,)):
                w("error", "Broken connection",
                  f"A '{r['kind']}' relationship points to a {et} (#{eid}) that no longer exists.",
                  [{"type": "relationship", "id": r["id"]}])

    # 5) Governance gap: an organization with no leader on record. A missing
    #    leader is a real structural gap in a political/fantasy power struggle;
    #    it's routine for genres that aren't organized around who's in charge,
    #    so those get it as a soft suggestion rather than a warning.
    gov_severity = "warning" if bucket in ("political", "fantasy") else "info"
    for o in orgs:
        lead = (o["leadership"] or "").strip()
        ok = False
        if lead.isdigit() and int(lead) in chars:
            ok = True
        elif lead and not lead.isdigit():
            ok = True
        if not ok:
            w(gov_severity, "Governance gap",
              f"Organization “{o['name']}” has no leader on record — who runs it?",
              [{"type": "organization", "id": o["id"]}])

    # 5b) Relationship conflict: a character pair carries both a bonding tie
    #    (family/ally/romance/friend) and an adversarial one (enemy/rival) with
    #    no recorded event or scene that could explain the shift. Real genre
    #    signal, not just lifespans and leadership: a romance runs on exactly
    #    this kind of contradiction, so it's promoted to a warning there.
    POSITIVE_KINDS = {"romance", "ally", "family", "friend"}
    NEGATIVE_KINDS = {"enemy", "rival"}
    narrative_texts = [f"{e['title']} {e['description']}".lower() for e in events] + \
                       [f"{s['title']} {s['purpose']} {s['conflict']} {s['info']}".lower() for s in scenes]
    pair_kinds = {}
    for r in rels:
        if r["source_type"] == "character" and r["target_type"] == "character":
            key = tuple(sorted((r["source_id"], r["target_id"])))
            pair_kinds.setdefault(key, set()).add(r["kind"])
    conflict_severity = "warning" if bucket == "romance" else "info"
    for (a_id, b_id), kinds in pair_kinds.items():
        pos, neg = kinds & POSITIVE_KINDS, kinds & NEGATIVE_KINDS
        if not (pos and neg):
            continue
        a, b = chars.get(a_id), chars.get(b_id)
        if not (a and b):
            continue
        a_tok, b_tok = _distinctive_tokens(a["name"]), _distinctive_tokens(b["name"])
        bridged = any(
            (not a_tok or all(t in text for t in a_tok)) and (not b_tok or all(t in text for t in b_tok))
            for text in narrative_texts
        )
        if not bridged:
            w(conflict_severity, "Relationship conflict",
              f"{a['name']} and {b['name']} carry both a '{'/'.join(sorted(pos))}' tie and a "
              f"'{'/'.join(sorted(neg))}' tie, with no recorded event or scene bridging the shift.",
              [{"type": "character", "id": a_id}, {"type": "character", "id": b_id}])

    # 6) Orphan characters: exist but connect to nothing (no rels, no scenes).
    connected = set()
    for r in rels:
        if r["source_type"] == "character":
            connected.add(r["source_id"])
        if r["target_type"] == "character":
            connected.add(r["target_id"])
    for cids in sc_map.values():
        connected.update(cids)
    for c in chars.values():
        if c["id"] not in connected:
            w("info", "Orphaned character",
              f"{c['name']} is not connected to any scene, event, or relationship yet.",
              [{"type": "character", "id": c["id"]}])

    order = {"error": 0, "warning": 1, "info": 2}
    warnings.sort(key=lambda x: order.get(x["severity"], 3))
    return warnings


# --------------------------------------------------------------------------- #
#  AI Assistant — answers questions by querying the graph, not by guessing.
#  A small intent parser maps a natural question onto a real traversal.
# --------------------------------------------------------------------------- #
def find_character(uid, needle):
    needle = needle.strip().lower()
    if not needle:
        return None
    best = None
    for c in rows("SELECT * FROM characters WHERE universe_id=?", (uid,)):
        name = c["name"].lower()
        if needle == name:
            return c
        if needle in name or name in needle or needle in (c["role"] or "").lower():
            best = best or c
        # match on last word (e.g. "vane" -> first Vane; "king"/"ruler" -> role)
        for token in name.split():
            if token == needle:
                best = best or c
    if not best:
        for c in rows("SELECT * FROM characters WHERE universe_id=?", (uid,)):
            role = (c["role"] or "").lower()
            if any(k in role for k in ("ruler", "chancellor", "king", "queen", "leader")) and \
               any(k in needle for k in ("ruler", "king", "queen", "leader", "chancellor")):
                return c
    return best


def find_entity_by_name(uid, needle, table, name_col="name"):
    """Same fuzzy match as find_character, generalized to locations/organizations."""
    needle = needle.strip().lower()
    if not needle:
        return None
    best = None
    for r in rows(f"SELECT * FROM {table} WHERE universe_id=?", (uid,)):
        name = (r[name_col] or "").lower()
        if needle == name:
            return r
        if needle in name or name in needle:
            best = best or r
        for token in name.split():
            if token == needle:
                best = best or r
    return best


def relations_of(uid, ctype, cid):
    out = []
    for r in rows("SELECT * FROM relationships WHERE universe_id=?", (uid,)):
        if r["source_type"] == ctype and r["source_id"] == cid:
            out.append({"dir": "out", "kind": r["kind"], "label": r["label"],
                        "type": r["target_type"], "id": r["target_id"],
                        "name": entity_label(r["target_type"], r["target_id"])})
        elif r["target_type"] == ctype and r["target_id"] == cid:
            out.append({"dir": "in", "kind": r["kind"], "label": r["label"],
                        "type": r["source_type"], "id": r["source_id"],
                        "name": entity_label(r["source_type"], r["source_id"])})
    return out


def scenes_with_character(uid, cid):
    return rows(
        "SELECT s.* FROM scenes s JOIN scene_characters sc ON sc.scene_id=s.id "
        "WHERE s.universe_id=? AND sc.character_id=? ORDER BY s.time_year", (uid, cid))


def scenes_at_location(uid, lid):
    return rows("SELECT * FROM scenes WHERE universe_id=? AND location_id=? ORDER BY time_year", (uid, lid))


def org_members(uid, oid):
    """Characters linked to an organization with a 'member' relationship, plus its leader."""
    members = []
    for r in relations_of(uid, "organization", oid):
        if r["type"] == "character" and r["kind"] in ("member", "leader"):
            members.append(r)
    return members


def characters_met(uid, cid):
    """Two characters have 'met' if they share a scene or a direct relationship."""
    met = set()
    my_scenes = {s["id"] for s in scenes_with_character(uid, cid)}
    for r in rows("SELECT * FROM scene_characters", ()):
        if r["scene_id"] in my_scenes and r["character_id"] != cid:
            met.add(r["character_id"])
    for r in relations_of(uid, "character", cid):
        if r["type"] == "character":
            met.add(r["id"])
    return met


IMPACT_WORDS = ("dies", "die", "death", "is killed", "kills", "kill", "killed off",
                "writes out", "written out", "removed", "remove", "eliminate",
                "eliminated", "assassinate", "assassinated", "perishes", "perish",
                "if we kill", "if we lose", "loses", "vanishes", "consequence",
                "what if", "what happens if")
NEVER_MET_WORDS = ("never met", "hasn't met", "has never met", "never interacted",
                    "never crossed paths", "no connection to", "hasn't interacted",
                    "never spoken to", "never encountered", "haven't met")
SCENE_WORDS = ("involving", "with", "in", "every", "show", "featuring", "appears", "list")
LEADERSHIP_WORDS = ("who leads", "who runs", "leader of", "who is in charge",
                     "who commands", "who governs", "head of", "who presides over",
                     "who's in control of", "who is in control of", "who's the head of")
CONNECTION_WORDS = ("connected", "connections", "relationship", "related", "linked",
                     "who knows", "allied with", "enemies with", "associated with",
                     "ties to", "tied to")
LOCATION_WORDS = ("scenes at", "scenes in", "what happens at", "what happens in",
                   "who has been to", "who visited", "who's been to", "set in")
MEMBER_WORDS = ("members of", "who is in", "who belongs to", "part of", "who's in")
CANON_WORDS = ("canon issue", "contradiction", "what's wrong", "whats wrong",
               "any problems", "consistency", "canon check", "audit", "canon status")


def ai_answer(uid, q):
    ql = q.lower().strip()

    # Intent: canon health, asked in plain language.
    if any(k in ql for k in CANON_WORDS):
        warns = canon_check(uid)
        errs = sum(1 for w in warns if w["severity"] == "error")
        return {
            "intent": "canon-summary",
            "headline": f"{len(warns)} open canon item(s), {errs} contradiction(s)" if warns else "Canon is consistent",
            "subject": None,
            "items": [{"type": "note", "id": i, "name": w["kind"], "note": w["message"]}
                      for i, w in enumerate(warns)],
            "explain": "Live results from the Canon Engine — the same audit as the Canon Engine tab.",
        }

    # Intent: what happens if X dies / is removed?
    if any(k in ql for k in IMPACT_WORDS):
        c = _subject_character(uid, ql, ("dies", "die", "death", "killed", "kill", "remove",
                                          "removed", "if", "what", "happens", "the",
                                          "consequences", "consequence", "of", "we", "lose", "loses"))
        if c:
            return _impact_report(uid, c)

    # Intent: who has never met X?
    if any(k in ql for k in NEVER_MET_WORDS) or ("never" in ql and "met" in ql):
        c = _subject_character(uid, ql, ("who", "has", "have", "never", "met", "the", "hasnt",
                                          "hasn't", "seen", "haven't", "crossed", "paths",
                                          "interacted", "encountered", "with"))
        if c:
            met = characters_met(uid, c["id"])
            allc = rows("SELECT * FROM characters WHERE universe_id=?", (uid,))
            never = [x for x in allc if x["id"] != c["id"] and x["id"] not in met]
            return {
                "intent": "who-has-never-met",
                "headline": f"{len(never)} character(s) have no on-page connection to {c['name']}",
                "subject": {"type": "character", "id": c["id"], "name": c["name"]},
                "items": [{"type": "character", "id": x["id"], "name": x["name"], "note": x["role"]} for x in never],
                "explain": "‘Met’ here means sharing a scene or a direct relationship. "
                           "These characters currently share neither with the subject.",
            }

    # Intent: scenes at / who visited a location.
    if any(k in ql for k in LOCATION_WORDS):
        cand = ql
        for k in LOCATION_WORDS:
            cand = cand.replace(k, " ")
        l = _subject_from(uid, cand, "locations", ("who", "has", "been", "to", "the",
                                                     "visited", "set", "in", "what",
                                                     "happens", "at"))
        if l:
            sc = scenes_at_location(uid, l["id"])
            return {
                "intent": "location-scenes",
                "headline": f"{l['name']} hosts {len(sc)} scene(s)",
                "subject": {"type": "location", "id": l["id"], "name": l["name"]},
                "items": [{"type": "scene", "id": s["id"], "name": s["title"],
                           "note": f"AE {s['time_year']} · {s['purpose']}" if s["time_year"] else s["purpose"]}
                          for s in sc],
            }

    # Intent: who belongs to / is a member of X (organization).
    if any(k in ql for k in MEMBER_WORDS):
        cand = ql
        for k in MEMBER_WORDS:
            cand = cand.replace(k, " ")
        o = _subject_from(uid, cand, "organizations", ("who", "is", "the", "of", "part", "belongs", "to"))
        if o:
            members = org_members(uid, o["id"])
            lead = o["leadership"]
            lead_name = entity_label("character", int(lead)) if lead.isdigit() else None
            items = ([{"type": "character", "id": int(lead), "name": lead_name, "note": "leader"}]
                     if lead_name else []) + \
                    [{"type": "character", "id": m["id"], "name": m["name"], "note": m["kind"]} for m in members]
            return {
                "intent": "org-members",
                "headline": f"{len(items)} character(s) tied to {o['name']}",
                "subject": {"type": "organization", "id": o["id"], "name": o["name"]},
                "items": items,
            }

    # Intent: scenes involving X.
    if "scene" in ql and any(k in ql for k in SCENE_WORDS):
        c = _subject_character(uid, ql, ("show", "me", "every", "all", "scene", "scenes", "involving", "with", "featuring", "in", "that", "appears", "the", "of", "list"))
        if c:
            sc = scenes_with_character(uid, c["id"])
            return {
                "intent": "scenes-involving",
                "headline": f"{c['name']} appears in {len(sc)} scene(s)",
                "subject": {"type": "character", "id": c["id"], "name": c["name"]},
                "items": [{"type": "scene", "id": s["id"], "name": s["title"],
                           "note": f"AE {s['time_year']} · {s['purpose']}" if s["time_year"] else s["purpose"]}
                          for s in sc],
            }

    # Intent: who leads / who runs X (organization).
    if any(k in ql for k in LEADERSHIP_WORDS):
        for o in rows("SELECT * FROM organizations WHERE universe_id=?", (uid,)):
            if o["name"].lower().split()[-1] in ql or o["name"].lower() in ql:
                lead = o["leadership"]
                who = entity_label("character", int(lead)) if lead.isdigit() else (lead or "— unrecorded —")
                return {"intent": "leadership",
                        "headline": f"{o['name']} is led by {who}",
                        "subject": {"type": "organization", "id": o["id"], "name": o["name"]},
                        "items": []}
        # The question was clearly asking about leadership, but no organization
        # in this universe matched the name — say so plainly instead of
        # falling through to a fuzzy, unrelated entity match below (a
        # location or character whose name happens to share a substring).
        # A wrong-but-plausible-looking answer is worse than an honest miss.
        return {"intent": "leadership", "headline": "No organization by that name in this universe",
                "subject": None, "items": []}

    # Intent: what happened in year Y / what led to X.
    ym = re.search(r"\b(-?\d{1,5})\b", ql)
    if ym and any(k in ql for k in ("happened in", "events in", "what happened")):
        yr = int(ym.group(1))
        evs = rows("SELECT * FROM events WHERE universe_id=? AND year=? ORDER BY id", (uid, yr))
        return {
            "intent": "timeline-year",
            "headline": f"{len(evs)} event(s) recorded in {yr}",
            "subject": None,
            "items": [{"type": "event", "id": e["id"], "name": e["title"], "note": e["category"]} for e in evs],
        }

    # Intent: how are X and Y connected — a real graph traversal (via
    # NetworkX, when installed) that can surface an INDIRECT chain, not just
    # "is there a direct relationship." Checked before the single-subject
    # connections intent below, since this one needs two names.
    if any(k in ql for k in ("how are", "how is", "connection between", "path between")) \
            and any(k in ql for k in ("connect", "path", "linked")):
        all_chars = rows("SELECT * FROM characters WHERE universe_id=?", (uid,))
        mentioned = [c for c in all_chars
                     if c["name"].lower() in ql or c["name"].split()[0].lower() in ql.split()]
        if len(mentioned) >= 2:
            a, b = mentioned[0], mentioned[1]
            result = graph_shortest_path(uid, a["name"], b["name"])
            if result is None:
                return {"intent": "unknown",
                        "headline": "Graph traversal needs networkx, which isn't installed.",
                        "subject": None, "items": [], "explain": None}
            if not result.get("connected"):
                return {"intent": "path",
                        "headline": f"No path found between {a['name']} and {b['name']}",
                        "subject": {"type": "character", "id": a["id"], "name": a["name"]}, "items": []}
            return {
                "intent": "path",
                "headline": f"{a['name']} connects to {b['name']} in {len(result['steps'])} step(s)",
                "subject": {"type": "character", "id": a["id"], "name": a["name"]},
                "items": [{"type": "note", "id": i, "name": f"{s['from']} → {s['to']}", "note": s["kind"]}
                          for i, s in enumerate(result["steps"])],
                "explain": "Traced through the full relationship graph, so this can surface an "
                           "indirect chain a direct-relationship lookup would miss.",
            }

    # Intent: relationships / connections of X.
    if any(k in ql for k in CONNECTION_WORDS):
        c = _subject_character(uid, ql, ("who", "is", "connected", "to", "the", "connections", "of", "relationships", "related", "knows", "allied", "with", "enemies", "associated", "ties", "tied"))
        if c:
            rels = relations_of(uid, "character", c["id"])
            return {"intent": "connections",
                    "headline": f"{c['name']} has {len(rels)} direct connection(s)",
                    "subject": {"type": "character", "id": c["id"], "name": c["name"]},
                    "items": [{"type": r["type"], "id": r["id"], "name": r["name"],
                               "note": f"{r['kind']} — {r['label']}" if r["label"] else r["kind"]} for r in rels]}

    # Fallback: a character, then an organization, then a location lookup.
    c = _subject_character(uid, ql, ())
    if c:
        rels = relations_of(uid, "character", c["id"])
        sc = scenes_with_character(uid, c["id"])
        return {"intent": "profile",
                "headline": f"{c['name']} — {c['role']}",
                "subject": {"type": "character", "id": c["id"], "name": c["name"]},
                "items": ([{"type": "note", "id": 0, "name": "Goal", "note": c["goals"]}] if c["goals"] else []) +
                         [{"type": r["type"], "id": r["id"], "name": r["name"], "note": r["kind"]} for r in rels] +
                         [{"type": "scene", "id": s["id"], "name": s["title"], "note": f"AE {s['time_year']}" if s["time_year"] else ""} for s in sc]}
    o = _subject_from(uid, ql, "organizations", ())
    if o:
        rels = relations_of(uid, "organization", o["id"])
        return {"intent": "profile",
                "headline": f"{o['name']} — {o['kind'] or 'Organization'}",
                "subject": {"type": "organization", "id": o["id"], "name": o["name"]},
                "items": [{"type": r["type"], "id": r["id"], "name": r["name"], "note": r["kind"]} for r in rels]}
    l = _subject_from(uid, ql, "locations", ())
    if l:
        sc = scenes_at_location(uid, l["id"])
        return {"intent": "profile",
                "headline": f"{l['name']} — {l['kind'] or 'Location'}",
                "subject": {"type": "location", "id": l["id"], "name": l["name"]},
                "items": [{"type": "scene", "id": s["id"], "name": s["title"], "note": f"AE {s['time_year']}" if s["time_year"] else ""} for s in sc]}

    return {"intent": "unknown",
            "headline": "I query the universe graph — try naming a character, place, or organization.",
            "subject": None,
            "items": [],
            "explain": "Examples: “Show every scene involving Mara.” · “Who has never met the Chancellor?” "
                       "· “What happens if Aldric dies?” · “Who is connected to Torix?” "
                       "· “Who's been to Halden Station?” · “Any canon issues?”"}


STOPWORDS = {"the", "a", "an", "of", "to", "in", "is", "who", "what", "show", "me",
             "every", "all", "does", "do", "has", "have", "with", "and", "if", "happens",
             "happen", "when", "would", "will", "character", "scene", "scenes",
             "any", "at", "for", "on", "been", "belongs", "part", "member", "members"}


def _subject_character(uid, ql, extra_stops):
    """Pull the most likely character name out of a free-text question."""
    stops = STOPWORDS | set(extra_stops)
    tokens = [t.strip("?.,!'\"") for t in ql.split()]
    tokens = [t for t in tokens if t and t not in stops]
    # try multi-word then single tokens, longest first
    for n in (3, 2, 1):
        for i in range(len(tokens) - n + 1):
            cand = " ".join(tokens[i:i + n])
            c = find_character(uid, cand)
            if c:
                return c
    # role words
    for kw in ("ruler", "king", "queen", "chancellor", "leader"):
        if kw in ql:
            c = find_character(uid, kw)
            if c:
                return c
    return None


def _subject_from(uid, ql, table, extra_stops):
    """Same free-text scan as _subject_character, generalized to any named entity table."""
    stops = STOPWORDS | set(extra_stops)
    tokens = [t.strip("?.,!'\"") for t in ql.split()]
    tokens = [t for t in tokens if t and t not in stops]
    for n in (3, 2, 1):
        for i in range(len(tokens) - n + 1):
            cand = " ".join(tokens[i:i + n])
            r = find_entity_by_name(uid, cand, table)
            if r:
                return r
    return None


def _impact_report(uid, c):
    """What changes if this character is removed — a real graph traversal."""
    rels = relations_of(uid, "character", c["id"])
    sc = scenes_with_character(uid, c["id"])
    led = [o for o in rows("SELECT * FROM organizations WHERE universe_id=?", (uid,))
           if o["leadership"] == str(c["id"])]
    impossible = sc  # every scene they appear in is now in question
    consequences = []
    for o in led:
        consequences.append({"type": "organization", "id": o["id"], "name": o["name"],
                             "note": "Leadership vacuum — needs a new head."})
    for r in rels:
        if r["type"] == "character" and r["kind"] in ("enemy", "rival"):
            consequences.append({"type": "character", "id": r["id"], "name": r["name"],
                                 "note": "Rival loses their antagonist — arc must change."})
        elif r["type"] == "character" and r["kind"] in ("family", "ally", "romance"):
            consequences.append({"type": "character", "id": r["id"], "name": r["name"],
                                 "note": f"Loses a {r['kind']} tie — motivation shifts."})
    for s in impossible:
        consequences.append({"type": "scene", "id": s["id"], "name": s["title"],
                             "note": "Scene now needs rewriting or removal."})
    return {
        "intent": "impact-analysis",
        "headline": f"Removing {c['name']} touches {len(consequences)} element(s)",
        "subject": {"type": "character", "id": c["id"], "name": c["name"]},
        "items": consequences,
        "explain": "The Canon Engine traces every scene, relationship, and organization "
                   f"wired to {c['name']} and reports what must change downstream.",
    }


# --------------------------------------------------------------------------- #
#  Draft import — turn a pasted manuscript into a starting roster instead of
#  making the writer build it by hand. Everything below is regex and frequency
#  counting over plain text: no network calls, no model, nothing that leaves
#  the process. It proposes candidates; the writer reviews and edits them in
#  the UI before anything is written to the database.
# --------------------------------------------------------------------------- #
DIALOGUE_VERBS = ("said", "asked", "replied", "shouted", "whispered", "murmured",
                   "answered", "cried", "yelled", "muttered", "called", "added",
                   "continued", "snapped", "demanded", "explained")
LOCATION_PREPS = ("in", "at", "to", "from", "near", "outside", "inside",
                   "toward", "towards", "beyond", "across", "through")
ORG_KEYWORDS = {"order", "guild", "council", "kingdom", "house", "company", "corp",
                 "corporation", "empire", "fleet", "movement", "church", "academy",
                 "federation", "alliance", "faction", "clan", "coven", "society",
                 "union", "party", "syndicate", "cartel", "agency", "department",
                 "ministry", "court", "compact", "collective"}
NAME_STOPWORDS = {"the", "a", "an", "he", "she", "they", "it", "i", "but", "and",
                   "when", "if", "this", "that", "there", "chapter", "scene",
                   "then", "so", "yet", "however", "meanwhile", "later", "now",
                   "monday", "tuesday", "wednesday", "thursday", "friday",
                   "saturday", "sunday", "january", "february", "march", "april",
                   "may", "june", "july", "august", "september", "october",
                   "november", "december",
                   # Pronouns/indefinites: capitalized only because they start a
                   # sentence, not because they name someone. "He"/"she" above
                   # already covered the third person singular; first/second
                   # person and collective/indefinite forms were missing, which
                   # is exactly how "We", "You", and "Everyone" ended up filed
                   # as named characters in first-person narration.
                   "we", "you", "us", "our", "ours", "yours", "mine", "myself",
                   "yourself", "himself", "herself", "themselves", "ourselves",
                   "everyone", "everybody", "someone", "somebody", "anyone",
                   "anybody", "nobody", "everything", "something", "anything",
                   "nothing", "who", "whom", "whoever",
                   # A second, wider pass: him/her/his/why/what/etc. weren't
                   # covered by the first pronoun fix, and a real draft (not
                   # a hand-picked test sentence) found every one of these
                   # showing up as a "character" — object/possessive pronouns
                   "him", "her", "hers", "his", "its", "their", "theirs",
                   "itself", "what", "where", "why", "how", "which", "whose",
                   "no", "my", "yes", "ok", "okay", "well", "oh", "hey",
                   "alright", "please", "sorry", "thanks",
                   # contractions NAME_RE's own character class (letters +
                   # apostrophe) can match as a single capitalized token —
                   # "I'll", "Don't" — when one starts a sentence
                   "i'll", "you'll", "we'll", "they'll", "he'll", "she'll",
                   "i'm", "i've", "don't", "won't", "can't", "isn't", "didn't",
                   "wasn't", "wouldn't", "couldn't", "shouldn't", "aren't"}
NAME_RE = re.compile(r"\b([A-Z][a-zA-Z'’]+(?:\s+[A-Z][a-zA-Z'’]+){0,2})\b")
DIALOGUE_BEFORE_RE = re.compile(
    r"([A-Z][a-zA-Z'’]+(?:\s+[A-Z][a-zA-Z'’]+){0,2})\s+(?:" + "|".join(DIALOGUE_VERBS) + r")\b")
DIALOGUE_AFTER_RE = re.compile(
    r"\b(?:" + "|".join(DIALOGUE_VERBS) + r")\s+([A-Z][a-zA-Z'’]+(?:\s+[A-Z][a-zA-Z'’]+){0,2})")
LOCATION_RE = re.compile(
    r"\b(?:" + "|".join(LOCATION_PREPS) + r")\s+([A-Z][a-zA-Z']+(?:\s+[A-Z][a-zA-Z']+){0,2})\b")
# "Order of the Broken Crown", "Kingdom of Aldrenfar" — the keyword leads, not
# trails, so it needs its own pattern rather than falling out of NAME_RE.
_ORG_KW_ALT = "|".join(k.capitalize() for k in ORG_KEYWORDS)
ORG_OF_RE = re.compile(
    r"\b((?:" + _ORG_KW_ALT + r")\s+of\s+(?:the\s+)?[A-Z][a-zA-Z']+(?:\s+[A-Z][a-zA-Z']+){0,3})\b")
SCENE_BREAK_RE = re.compile(r"\n\s*\n|^\s*(?:chapter|scene)\b.*$|^\s*[-*_]{3,}\s*$", re.MULTILINE)

# A sentence naming a death, a founding, an invasion — that's a timeline event,
# not a scene or a piece of lore. A sentence defining a custom, a title, or a
# world-rule — that's lore. Neither is a proper-noun pattern like the entity
# extractors above, so both lean on verb/phrase signals instead.
EVENT_VERBS = ("died", "was born", "were born", "was killed", "was murdered",
               "was assassinated", "declared", "was declared", "signed", "was signed",
               "founded", "was founded", "discovered", "was discovered", "began",
               "ended", "fell", "was crowned", "erupted", "invaded", "was elected",
               "collapsed", "was destroyed", "was built", "broke out", "surrendered",
               "was executed")
EVENT_VERB_RE = re.compile(r"\b(?:" + "|".join(re.escape(v) for v in EVENT_VERBS) + r")\b", re.IGNORECASE)
RELATIVE_TIME_RE = re.compile(
    r"\b(?:\d+\s+)?years?\s+(?:later|earlier|before|after|ago)\b|"
    r"\ba decade\s+(?:later|earlier|after|before)\b|"
    r"\b(?:a |\d+\s+)?centur(?:y|ies)\s+(?:later|earlier|after|before|ago)\b|"
    r"\bthe (?:next|following)\s+(?:year|day|week|month)\b|"
    r"\bdecades?\s+(?:later|earlier|after|before)\b", re.IGNORECASE)

# Temporal reasoning: resolve a narrative-relative phrase ("ten years later",
# "three centuries ago") against a running "clock" — the most recent absolute
# year mentioned earlier in the draft. dateparser was tried here first and
# rejected: it resolves "ten years later" correctly but returns None for
# "ago"/"earlier"/"following" phrasing and even inverts direction on "a decade
# after" (tested directly against a fixed anchor date). This is a small,
# deterministic resolver instead, scoped to exactly the phrasing
# RELATIVE_TIME_RE already recognizes.
_NUMBER_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                  "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
                  "twelve": 12, "dozen": 12, "score": 20}
_UNIT_YEARS = {"year": 1, "decade": 10, "century": 100}
_RELATIVE_OFFSET_RE = re.compile(
    r"\b(a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|dozen|score|\d+)\s+"
    r"(year|years|decade|decades|centur(?:y|ies))\s+(later|after|earlier|before|ago)\b", re.IGNORECASE)
_FOLLOWING_YEAR_RE = re.compile(r"\bthe (?:next|following) year\b", re.IGNORECASE)


def _resolve_relative_year(sentence, anchor_year):
    """Anchor_year is the most recent absolute year seen earlier in reading
    order. Returns a resolved year, or None if the sentence doesn't match a
    recognized relative-offset pattern or there's no anchor yet to resolve
    against."""
    if anchor_year is None:
        return None
    if _FOLLOWING_YEAR_RE.search(sentence):
        return anchor_year + 1
    m = _RELATIVE_OFFSET_RE.search(sentence)
    if not m:
        return None
    num_word, unit_word, direction = m.group(1).lower(), m.group(2).lower(), m.group(3).lower()
    n = int(num_word) if num_word.isdigit() else _NUMBER_WORDS.get(num_word, 1)
    unit = "century" if unit_word.startswith("centur") else ("decade" if "decade" in unit_word else "year")
    sign = 1 if direction in ("later", "after") else -1
    return anchor_year + sign * (n * _UNIT_YEARS[unit])
LORE_SIGNAL_RE = re.compile(
    r"\b(?:is known as|is called|are known as|refers to|according to (?:legend|tradition|myth)|"
    r"it is said that|the (?:custom|tradition|law|legend) (?:of|holds|states)|"
    r"was founded|were founded|has always been|have always been|for generations|for centuries)\b",
    re.IGNORECASE)
DEFINITION_RE = re.compile(r"\b(?:is|are|was|were)\s+(?:a|an|the|known|called)\b", re.IGNORECASE)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _year_pattern(era_label):
    """Recognize a year in the universe's own calendar, not just a bare Gregorian
    guess — "AE 245" and "245 AE" are as valid a year as "1947"."""
    era = re.escape((era_label or "").strip())
    alts = [r"\b(?:1[0-9]|20)\d{2}\b"]
    if era and era.lower() != "year":
        alts += [rf"\b{era}\s*\d{{1,5}}\b", rf"\b\d{{1,5}}\s*{era}\b"]
    else:
        alts += [r"\byear\s*\d{1,5}\b", r"\b\d{1,5}\s*(?:AE|CE|BCE|AD|BC)\b"]
    return re.compile("|".join(alts), re.IGNORECASE)


def _extract_year(matched_text):
    m = re.search(r"\d{1,5}", matched_text)
    return int(m.group(0)) if m else None


def _guess_event_category(sentence):
    s = sentence.lower()
    if any(k in s for k in ("war", "battle", "invaded", "invasion")):
        return "war"
    if any(k in s for k in ("died", "death", "killed", "murder", "assassinat", "executed")):
        return "death"
    if any(k in s for k in ("born", "birth")):
        return "birth"
    if any(k in s for k in ("discovered", "discovery")):
        return "discovery"
    if any(k in s for k in ("declared", "signed", "elected", "crowned", "founded", "treaty", "accord", "law")):
        return "political"
    return "character"


def _sanitize_name(s):
    """Collapse embedded whitespace — including a literal newline, which can
    reach a stored name either via a regex match spanning a line break, or via
    someone editing the review screen and pasting in two lines at once — into
    single spaces, and strip stray quote/dash characters some sources carry
    at a word boundary. Applied both at extraction (_clean_candidate below)
    and again at the actual persistence boundary in api_draft_commit, since a
    hand-edited review payload never passes through extraction at all."""
    s = re.sub(r"\s+", " ", (s or "")).strip()
    # A double quote is never legitimate inside a name (unlike an apostrophe —
    # "O'Brien" is real) — remove it wherever it sits, not just at the edges,
    # which is what a dialogue tag fused onto a name via a line break leaves
    # behind.
    s = re.sub(r'["“”]', "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.strip("'’‘—–- ")


def _looks_like_a_name(cand):
    """An ALL-CAPS multi-word phrase ('GOD DIALOGUE', 'INT. HOUSE') is a
    script-format section header or stage direction, not a person's name —
    real names are Title Case, never fully capitalized, and this is exactly
    the shape that let a stage direction get filed as a character. A single
    ALL-CAPS word is left alone (a plausible acronym, e.g. an org's
    initials)."""
    words = cand.split()
    return not (len(words) > 1 and cand == cand.upper() and cand != cand.lower())


def _clean_candidate(phrase):
    words = _sanitize_name(phrase).split()
    words = [w.strip("\"'“”‘’—–-") for w in words]
    words = [w for w in words if w]
    while words and words[0].lower() in NAME_STOPWORDS:
        words = words[1:]
    return " ".join(words)


def _merge_by_first_name(names):
    """A draft mentions 'Marcus Doyle' once and 'Marcus' a dozen times after —
    or 'The Order of the Broken Crown' once and 'the Order' after — treat those
    as one entity and keep the fuller name, instead of proposing both. A title
    ("Admiral Josa Halden" vs. "Josa Halden") is skipped when picking the key,
    so a name mentioned with and without its title still merges."""
    best, order = {}, []
    for n in names:
        words = n.split()
        while words and words[0].lower().rstrip(".") in TITLES:
            words = words[1:]
        key = (words[0] if words else n.split()[0]).lower()
        if key not in best:
            order.append(key)
            best[key] = n
        elif len(n.split()) > len(best[key].split()):
            best[key] = n
    return [best[k] for k in order]


def _match_known_name(candidate, known):
    """Fuzzy-match an extracted noun phrase against a known name list — exact
    match first, then containment either direction, so 'the old admiral' can
    resolve to 'Admiral Josa Halden' and a bare first name resolves to its
    one full-name owner. Shared by event-subject resolution and character-
    relation derivation below, so both use the same matching rule."""
    if not candidate:
        return None
    cand = candidate.strip().lower()
    for name in known:
        if name.lower() == cand:
            return name
    for name in known:
        n = name.lower()
        if cand in n or n in cand:
            return name
    return None


def _merge_by_word_subset(names):
    """A second merge pass for exactly the case the title-strip above can't
    catch: 'Jemimah' and 'Barrister Jemimah Selman' don't merge by first-word,
    because 'Barrister' isn't in the curated TITLES set — and no fixed list
    of real-world and invented titles is ever going to be complete. This is
    the general fallback: if every word in a shorter name also appears in a
    longer one, they're the same entity, whatever the untitled word turns out
    to be. Runs after _merge_by_first_name, on its output."""
    by_len = sorted(names, key=lambda n: -len(n.split()))
    absorbed = set()
    for i, longer in enumerate(by_len):
        if longer in absorbed:
            continue
        longer_words = set(longer.lower().split())
        for shorter in by_len[i + 1:]:
            if shorter in absorbed or shorter == longer:
                continue
            shorter_words = set(shorter.lower().split())
            if shorter_words and shorter_words < longer_words:
                absorbed.add(shorter)
    return [n for n in names if n not in absorbed]


# --------------------------------------------------------------------------- #
#  Tier 2 — a real trained NER model (spaCy), layered on top of the regex
#  pass above. The regex tier is good at *structure* (scene breaks, who's
#  speaking, "Order of X" org names) but has no actual notion of what a
#  person, place, or date IS — it's guessing from capitalization and nearby
#  words. spaCy's NER was trained specifically to draw that distinction, so
#  it catches what the regex tier gets wrong in both directions: excluding
#  "Ravenmoor" as a place rather than a character, and recognizing relative
#  dates ("three centuries ago") the hand-written pattern list misses.
#
#  It also has a real weakness the regex tier doesn't: invented fantasy/
#  sci-fi proper nouns ("The Order of the Broken Crown") are out of its
#  training distribution, so it frequently misses or mislabels them. Neither
#  tier is strictly better — extract_entities() merges both rather than
#  picking one. Fully local; no network call; degrades honestly if spaCy or
#  its model isn't installed.
# --------------------------------------------------------------------------- #
_NLP = None
_NLP_LOAD_ATTEMPTED = False
NER_LABEL_MAP = {"PERSON": "characters", "ORG": "organizations",
                  "GPE": "locations", "LOC": "locations", "FAC": "locations"}


def _load_nlp():
    global _NLP, _NLP_LOAD_ATTEMPTED
    if _NLP_LOAD_ATTEMPTED:
        return _NLP
    _NLP_LOAD_ATTEMPTED = True
    try:
        import spacy
        _NLP = spacy.load("en_core_web_sm")
    except (ImportError, OSError):
        _NLP = None
    return _NLP


# --------------------------------------------------------------------------- #
#  Coreference resolution — "John entered the castle. He looked around. The
#  king greeted him." Without this, John/He/him are three separate mentions;
#  a scene where a character is only ever referred to by pronoun after their
#  first appearance would silently drop them from that scene's presence list,
#  and a relation like "the old king died" stays a vague description instead
#  of resolving to the actual named character.
#
#  coreferee (the lighter, spaCy-native option) requires spaCy 3.1 + an old
#  TensorFlow pin — genuinely incompatible with the spaCy 3.8 / Python 3.14
#  already in use here, confirmed by a failed install, not assumed. fastcoref
#  is the one that actually works: a real 90M-parameter neural coref model
#  (small — comparable to BERT-base), confirmed correct on the exact
#  "John/he/him" example this was built to handle. It needed `transformers`
#  pinned to 4.57.6 to load at all — the newest transformers (5.x) has
#  refactored internals that break fastcoref's model loading outright.
# --------------------------------------------------------------------------- #
_COREF = None
_COREF_LOAD_ATTEMPTED = False


_COREF_LOAD_ERROR = None


def _load_coref():
    """Broader than a plain ImportError catch on purpose — a missing model
    cache, an incompatible transformers version, or an OOM during load
    should all degrade to "unavailable" with an honest reason, the same as a
    missing package, rather than 500 the whole draft-import request."""
    global _COREF, _COREF_LOAD_ATTEMPTED, _COREF_LOAD_ERROR
    if _COREF_LOAD_ATTEMPTED:
        return _COREF
    _COREF_LOAD_ATTEMPTED = True
    try:
        from fastcoref import FCoref
        _COREF = FCoref(device="cpu")
    except Exception as e:
        _COREF_LOAD_ERROR = f"{type(e).__name__}: {e}"
        _COREF = None
    return _COREF


def resolve_coreferences(text):
    """Returns a dict mapping every pronoun/mention (lowercased) to its
    canonical named antecedent, e.g. {"he": "John", "him": "John"} — only for
    clusters that actually contain a proper-noun-looking mention to resolve
    to. A cluster of bare pronouns with no name in it resolves nothing; that's
    correct, not a gap — there's nothing to substitute in.
    Returns (mapping, available, note)."""
    coref = _load_coref()
    if coref is None:
        reason = f" ({_COREF_LOAD_ERROR})" if _COREF_LOAD_ERROR else ""
        return {}, False, (f"fastcoref isn't available{reason} — pronouns and descriptive "
                            "references ('the old king') stay unresolved. `pip install "
                            "fastcoref` (pulls in torch + transformers) to enable it.")
    preds = coref.predict(texts=[text[:20000]])
    clusters = preds[0].get_clusters(as_strings=True)
    mapping = {}
    for cluster in clusters:
        canonical = max((m for m in cluster if m[:1].isupper() and len(m.split()) <= 4),
                        key=len, default=None)
        if canonical is None:
            continue
        for mention in cluster:
            if mention != canonical:
                mapping[mention.lower()] = canonical
    return mapping, True, None


def ner_pass(text):
    """Run spaCy NER over the draft. Returns typed candidates plus the set of
    sentences containing a DATE entity, so the event detector can catch
    phrasing its own regex event-signal list misses."""
    nlp = _load_nlp()
    if nlp is None:
        return {"available": False, "characters": [], "locations": [], "organizations": [],
                "date_sentences": set(),
                "note": "spaCy (or its en_core_web_sm model) isn't installed — entity typing "
                        "is heuristics-only. `pip install spacy && python -m spacy download "
                        "en_core_web_sm` to enable it."}
    doc = nlp(text[:20000])  # cap input for latency on very long pastes
    characters, locations, organizations, date_sentences = [], [], [], set()
    for ent in doc.ents:
        name = ent.text.strip()
        if not name or len(name) > 60:
            continue
        bucket = NER_LABEL_MAP.get(ent.label_)
        if bucket == "characters":
            characters.append(name)
        elif bucket == "locations":
            locations.append(name)
        elif bucket == "organizations":
            organizations.append(name)
        elif ent.label_ == "DATE":
            date_sentences.add(ent.sent.text.strip())
    return {"available": True, "characters": characters, "locations": locations,
            "organizations": organizations, "date_sentences": date_sentences, "note": None,
            "doc": doc}


EVENT_VERB_LEMMAS = {"die", "kill", "murder", "assassinate", "declare", "sign",
                      "found", "discover", "begin", "end", "fall", "crown",
                      "erupt", "invade", "elect", "collapse", "destroy", "build",
                      "surrender", "execute", "marry", "betray", "flee", "escape",
                      "capture", "rescue", "attack", "defeat", "conquer"}


def _expand_np(token):
    """Widen a single dependency-tree token to its full noun phrase span —
    'king' becomes 'the old king', not just the bare head noun."""
    if token is None:
        return None
    chunk = next((nc for nc in token.doc.noun_chunks if nc.root == token), None)
    return chunk.text if chunk else token.text


def extract_relations(doc):
    """Real subject-verb-object triples from spaCy's dependency parse, not
    'these two names happen to share a sentence.' This is what lets "Clara
    gave Marcus the sword" become a structured relation, and lets event
    detection match a verb's LEMMA — so "founded", "founding", and "founds"
    are all the same event-verb — instead of the fixed string list in
    EVENT_VERB_RE, which only catches the exact inflections someone thought
    to enumerate."""
    if doc is None:
        return []
    relations = []
    for sent in doc.sents:
        root = sent.root
        if root.pos_ not in ("VERB", "AUX"):
            continue
        subj = next((t for t in root.children if t.dep_ in ("nsubj", "nsubjpass")), None)
        obj = next((t for t in root.children if t.dep_ in ("dobj", "attr", "dative")), None)
        if obj is None:
            prep = next((t for t in root.children if t.dep_ == "prep"), None)
            if prep is not None:
                obj = next((t for t in prep.children if t.dep_ == "pobj"), None)
        if subj is None and obj is None:
            continue
        relations.append({
            "subject": _expand_np(subj), "verb": root.lemma_, "object": _expand_np(obj),
            "is_event_verb": root.lemma_ in EVENT_VERB_LEMMAS,
            "sentence": sent.text.strip(),
        })
    return relations


# --------------------------------------------------------------------------- #
#  Knowledge graph — the SAME relationship data that already powers the
#  visual graph (api_graph, below), read through NetworkX for real
#  graph-theoretic answers instead of a straight relationship-table lookup:
#  centrality ("who's most connected") and shortest path ("how are X and Y
#  connected", including indirectly, through a chain of relationships).
#  NetworkX ships as a transitive dependency of spaCy/thinc, already present
#  wherever Tier 2 is — but that's an implementation detail of spaCy's own
#  dependency tree, not a guarantee, so this still degrades honestly with its
#  own check rather than assuming it's there.
# --------------------------------------------------------------------------- #
_NETWORKX_AVAILABLE = None


def _load_networkx():
    global _NETWORKX_AVAILABLE
    if _NETWORKX_AVAILABLE is None:
        try:
            import networkx  # noqa: F401
            _NETWORKX_AVAILABLE = True
        except ImportError:
            _NETWORKX_AVAILABLE = False
    return _NETWORKX_AVAILABLE


def build_networkx_graph(uid):
    """A NetworkX view of the same nodes/edges api_graph() renders to the
    frontend. Edges are added in both directions since "who's connected to
    whom" for narrative purposes doesn't care about the relationship's
    stored direction — a shortest path from a character to an event they
    caused is just as real read backwards."""
    import networkx as nx
    g = nx.MultiDiGraph()
    labels = {}
    queries = (
        ("character", "SELECT id,name FROM characters WHERE universe_id=?"),
        ("location", "SELECT id,name FROM locations WHERE universe_id=?"),
        ("organization", "SELECT id,name FROM organizations WHERE universe_id=?"),
        ("event", "SELECT id,title AS name FROM events WHERE universe_id=?"),
    )
    for etype, sql in queries:
        for r in rows(sql, (uid,)):
            nid = f"{etype}-{r['id']}"
            g.add_node(nid, type=etype, label=r["name"])
            labels[nid] = r["name"]
    for r in rows("SELECT * FROM relationships WHERE universe_id=?", (uid,)):
        s, t = f"{r['source_type']}-{r['source_id']}", f"{r['target_type']}-{r['target_id']}"
        if g.has_node(s) and g.has_node(t):
            g.add_edge(s, t, kind=r["kind"], label=r["label"])
            g.add_edge(t, s, kind=r["kind"], label=r["label"])
    return g, labels


def graph_centrality(uid, top_n=5):
    """Real centrality, not a raw relationship count — a character connected
    to two other well-connected characters ranks higher than one connected to
    two dead-end nodes."""
    if not _load_networkx():
        return None
    import networkx as nx
    g, labels = build_networkx_graph(uid)
    if g.number_of_nodes() == 0:
        return []
    scores = nx.degree_centrality(g)
    char_scores = sorted(
        ((nid, score) for nid, score in scores.items() if g.nodes[nid]["type"] == "character"),
        key=lambda x: x[1], reverse=True)
    return [{"type": "character", "id": int(nid.split("-")[1]), "name": labels[nid], "score": round(score, 4)}
            for nid, score in char_scores[:top_n]]


def graph_shortest_path(uid, from_name, to_name):
    """How are X and Y connected — walks the whole graph, so it finds an
    indirect chain (X knows Z who knows Y) that a direct-relationship lookup
    would report as "not connected.\""""
    if not _load_networkx():
        return None
    import networkx as nx
    g, labels = build_networkx_graph(uid)
    from_id = next((nid for nid, lbl in labels.items() if lbl.lower() == from_name.lower()), None)
    to_id = next((nid for nid, lbl in labels.items() if lbl.lower() == to_name.lower()), None)
    if not from_id or not to_id:
        return {"found_entities": False}
    try:
        path = nx.shortest_path(g, from_id, to_id)
    except nx.NetworkXNoPath:
        return {"found_entities": True, "connected": False}
    steps = []
    for i in range(len(path) - 1):
        edge_data = g.get_edge_data(path[i], path[i + 1])
        kind = next(iter(edge_data.values()))["kind"] if edge_data else "linked"
        steps.append({"from": labels[path[i]], "to": labels[path[i + 1]], "kind": kind})
    return {"found_entities": True, "connected": True,
            "path": [{"type": g.nodes[n]["type"], "name": labels[n]} for n in path], "steps": steps}


# --------------------------------------------------------------------------- #
#  Narrative state — a structured world-state snapshot at a point in the
#  timeline: who's alive, where they were last seen, what they're tied to.
#  Built by walking the same characters/relationships/events/scenes tables
#  canon_check() already traverses, not a separate store — "state" here means
#  a read-time projection of the graph as of a given year, not new storage.
#  Relationships are reported as they currently stand in full, not filtered
#  to "still true at that year" — tracking when a tie starts or ends would be
#  a real feature in its own right, not a byproduct of this one.
# --------------------------------------------------------------------------- #
def narrative_state(uid, as_of_year=None):
    def as_year(v):
        if v is None or (isinstance(v, str) and not v.strip().lstrip("-").isdigit()):
            return None
        return int(v)

    chars = rows("SELECT * FROM characters WHERE universe_id=?", (uid,))
    for c in chars:
        c["birth_year"] = as_year(c["birth_year"])
        c["death_year"] = as_year(c["death_year"])

    if as_of_year is None:
        candidates = [c["death_year"] for c in chars if c["death_year"] is not None]
        candidates += [c["birth_year"] for c in chars if c["birth_year"] is not None]
        candidates += [e["year"] for e in rows(
            "SELECT year FROM events WHERE universe_id=? AND year IS NOT NULL", (uid,))]
        candidates += [s["time_year"] for s in rows(
            "SELECT time_year FROM scenes WHERE universe_id=? AND time_year IS NOT NULL", (uid,))]
        as_of_year = max(candidates) if candidates else None

    scene_appearances = {}
    for r in rows(
            "SELECT sc.character_id, s.time_year, s.location_id FROM scene_characters sc "
            "JOIN scenes s ON s.id = sc.scene_id WHERE s.universe_id=?", (uid,)):
        scene_appearances.setdefault(r["character_id"], []).append(r)

    char_orgs = {}
    for o in rows("SELECT * FROM organizations WHERE universe_id=?", (uid,)):
        lead = (o["leadership"] or "").strip()
        if lead.isdigit():
            char_orgs.setdefault(int(lead), []).append(o["name"])

    state = {}
    for c in chars:
        if as_of_year is not None and c["birth_year"] is not None and c["birth_year"] > as_of_year:
            status = "not yet born"
        elif as_of_year is not None and c["death_year"] is not None and c["death_year"] <= as_of_year:
            status = "dead"
        else:
            status = "alive"
        appearances = [r for r in scene_appearances.get(c["id"], [])
                       if as_of_year is None or r["time_year"] is None or r["time_year"] <= as_of_year]
        appearances.sort(key=lambda r: (r["time_year"] is None, r["time_year"] or 0))
        last_loc_id = appearances[-1]["location_id"] if appearances else None
        state[c["name"]] = {
            "status": status,
            "last_known_location": entity_label("location", last_loc_id) if last_loc_id else None,
            "leads": char_orgs.get(c["id"], []),
            "relationships": [{"to": r["name"], "kind": r["kind"]} for r in relations_of(uid, "character", c["id"])],
        }

    events_so_far = [e for e in rows("SELECT * FROM events WHERE universe_id=? ORDER BY year", (uid,))
                      if as_of_year is None or e["year"] is None or e["year"] <= as_of_year]

    return {
        "as_of_year": as_of_year,
        "characters": state,
        "events_so_far": [{"year": e["year"], "title": e["title"], "category": e["category"]}
                          for e in events_so_far],
    }


def extract_entities(text, era_label="Year"):
    """Heuristic, fully local entity extraction from a pasted draft, merged
    with the spaCy NER pass above when it's available."""
    text = text.replace("\r\n", "\n")
    chunks = [c.strip() for c in SCENE_BREAK_RE.split(text) if c.strip()]
    if not chunks and text.strip():
        chunks = [text.strip()]

    name_counts = Counter()
    org_candidates = Counter()
    loc_candidates = Counter()
    dialogue_names = set()
    occupied = []  # character spans already claimed by an "X of Y" org match

    for m in ORG_OF_RE.finditer(text):
        org_candidates[_clean_candidate(m.group(1))] += 1
        occupied.append(m.span(1))

    def _in_occupied(span):
        return any(s <= span[0] < e for s, e in occupied)

    for m in NAME_RE.finditer(text):
        if _in_occupied(m.span(1)):
            continue
        cand = _clean_candidate(m.group(1))
        if not cand or cand.lower() in NAME_STOPWORDS or not _looks_like_a_name(cand):
            continue
        if cand.split()[-1].lower() in ORG_KEYWORDS:
            org_candidates[cand] += 1
        else:
            name_counts[cand] += 1

    for rx in (DIALOGUE_BEFORE_RE, DIALOGUE_AFTER_RE):
        for m in rx.finditer(text):
            cand = _clean_candidate(m.group(1))
            if cand and cand.lower() not in NAME_STOPWORDS and _looks_like_a_name(cand):
                dialogue_names.add(cand)

    for m in LOCATION_RE.finditer(text):
        if _in_occupied(m.span(1)):
            continue
        cand = _clean_candidate(m.group(1))
        if cand and cand.lower() not in NAME_STOPWORDS:
            loc_candidates[cand] += 1

    # Characters: anyone caught speaking, then any multi-word name (a full name
    # is trustworthy even mentioned once), then single words repeated 2+ times
    # — a lone capitalized word needs repetition before it's trusted as a name
    # rather than a stray sentence-starter. A name that only ever shows up
    # after "in"/"at"/"to" etc. reads as a place ("still in Ravenmoor") even if
    # it repeats, so location-attested names lose to that unless dialogue
    # proves otherwise.
    loc_only = {n.lower() for n in loc_candidates}
    ranked, seen = [], set()
    for name in dialogue_names:
        if name.lower() not in seen and len(name.split()) <= 3:
            seen.add(name.lower())
            ranked.append(name)
    for name, n in name_counts.most_common():
        if name.lower() in seen or name.lower() in loc_only:
            continue
        if len(name.split()) == 1 and n < 2:
            continue
        seen.add(name.lower())
        ranked.append(name)
    characters = _merge_by_first_name(ranked)

    char_lastwords = {c.split()[-1].lower() for c in characters}
    locations = [name for name, n in loc_candidates.most_common()
                 if name.lower() not in seen and name.split()[-1].lower() not in char_lastwords]
    # "The Order of the Broken Crown" gets a full mention once, then "the Order"
    # for short — same merge-by-first-word logic as characters' full/short names.
    organizations = _merge_by_first_name(
        [name for name, n in org_candidates.most_common() if name.lower() not in seen])

    # Tier 2: layer spaCy's typed entities on top, additively — it only fills
    # gaps the regex tier missed, never overrides a regex catch, since NER
    # confidently mislabels invented fantasy/sci-fi names about as often as
    # the regex tier does (see ner_pass()'s docstring).
    ner = ner_pass(text)
    if ner["available"]:
        known = {n.lower() for n in characters + locations + organizations}
        characters = _merge_by_first_name(
            characters + [n for n in ner["characters"] if n.lower() not in known])
        known = {n.lower() for n in characters + locations + organizations}
        locations = _merge_by_first_name(
            locations + [n for n in ner["locations"] if n.lower() not in known])
        known = {n.lower() for n in characters + locations + organizations}
        # Structural evidence, not just capitalization: an org candidate NER
        # contributes only counts if it names an organization when it also
        # carries one of the same structural keywords the regex tier looks
        # for. Without this, general-purpose NER files mythological/religious/
        # philosophical proper nouns inside a narrator's digression ("Norse",
        # "The Life, Death and Resurrection of Christ") as organizations, on
        # capitalization alone — it has no notion that they're references, not
        # factions in the story world.
        plausible_orgs = [n for n in ner["organizations"] if n.lower() not in known
                           and set(n.lower().replace(",", " ").split()) & ORG_KEYWORDS]
        organizations = _merge_by_first_name(organizations + plausible_orgs)

    # A second merge pass: the title-strip merge above only knows a small
    # curated list of titles, so "Barrister Jemimah Selman" and "Jemimah"
    # don't merge (Barrister isn't in TITLES) even though they're the same
    # person. Word-subset merging catches that case and any title neither
    # list could have anticipated, without needing to enumerate real-world
    # or invented titles at all.
    characters = _merge_by_word_subset(characters)
    organizations = _merge_by_word_subset(organizations)

    # Coreference resolution: a scene that only ever refers to a character by
    # pronoun after their first named appearance ("She walked to the window.
    # She sighed.") would otherwise silently drop them from that scene's
    # presence list, since the literal-name check below has nothing to match.
    coref_map, coref_available, coref_note = resolve_coreferences(text)

    scenes = []
    for i, chunk in enumerate(chunks, 1):
        present = [c for c in characters if re.search(r"\b" + re.escape(c.split()[0]) + r"\b", chunk)]
        if coref_map:
            resolved_here = {coref_map[m] for m in coref_map
                              if re.search(r"\b" + re.escape(m) + r"\b", chunk.lower())}
            present += [c for c in characters if c in resolved_here and c not in present]
        first_sentence = re.split(r"(?<=[.!?])\s+", chunk.strip())[0][:80]
        scenes.append({"title": first_sentence or f"Scene {i}", "text": chunk[:800], "characters": present})

    # Timeline events: a sentence naming a death, founding, invasion, or a year
    # in the universe's own calendar is a dated moment, not a scene or lore.
    # A single reading-order pass, not several merged after the fact, because
    # temporal reasoning needs a "running clock" — the most recent absolute
    # year seen — to resolve relative phrasing ("ten years later") in later
    # sentences, and that only works if sentences are visited in the order
    # they were written.
    year_re = _year_pattern(era_label)
    sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(text.replace("\n", " ")) if s.strip()]
    ner_date_sentences = ner["date_sentences"] if ner["available"] else set()
    relations = extract_relations(ner["doc"]) if ner["available"] else []
    event_relation_by_sentence = {r["sentence"]: r for r in relations if r["is_event_verb"]}

    # Character-to-character relations, typed by the actual verb: "Clara gave
    # Marcus the sword" becomes a real ('Clara','gave','Marcus') tie instead
    # of being thrown away the moment its verb isn't an event verb — this SVO
    # data was already computed above for event detection; every non-event
    # relation was previously discarded entirely, which is the main reason a
    # draft-imported cast reads as a flat "everyone's linked" graph instead of
    # the typed family/ally/enemy ties a hand-authored universe has. Only
    # kept when BOTH sides resolve to a known character, so a subject/object
    # that's really a place, an object, or an unmatched name doesn't create a
    # false character-to-character edge.
    character_relations = []
    for r in relations:
        if r["is_event_verb"] or not (r["subject"] and r["object"]):
            continue
        subj = _match_known_name(coref_map.get(r["subject"].lower(), r["subject"]), characters)
        obj = _match_known_name(coref_map.get(r["object"].lower(), r["object"]), characters)
        if subj and obj and subj != obj:
            character_relations.append({"subject": subj, "object": obj, "verb": r["verb"]})

    events, lore, event_seen, running_anchor = [], [], set(), None
    for sent in sentences:
        year_m = year_re.search(sent)
        rel = event_relation_by_sentence.get(sent)
        has_relative = bool(RELATIVE_TIME_RE.search(sent))
        is_event = bool(year_m) or bool(EVENT_VERB_RE.search(sent)) or has_relative \
            or sent in ner_date_sentences or rel is not None
        if is_event:
            key = sent.lower()[:60]
            if key in event_seen:
                continue
            event_seen.add(key)
            if year_m:
                year = _extract_year(year_m.group(0))
            elif has_relative:
                year = _resolve_relative_year(sent, running_anchor)
            else:
                year = None
            if year is not None:
                running_anchor = year
            title = sent[:100]
            # Which known characters/locations does this event actually touch?
            # Same direct-mention + coreference check already used for a
            # scene's "present" list just above — an event that's never tied
            # to anyone is exactly how a timeline ends up disconnected from
            # its own cast, which is what leaves canon checks and the graph
            # with nothing to reconcile a death or a birth against.
            event_chars = [c for c in characters if re.search(r"\b" + re.escape(c.split()[0]) + r"\b", sent)]
            if coref_map:
                resolved_here = {coref_map[m] for m in coref_map
                                  if re.search(r"\b" + re.escape(m) + r"\b", sent.lower())}
                event_chars += [c for c in characters if c in resolved_here and c not in event_chars]
            event_locs = [l for l in locations if re.search(r"\b" + re.escape(l.split()[0]) + r"\b", sent)]
            if rel and rel["subject"]:
                # "the old king died" is a vague subject on its own — if
                # coreference resolved it to a named character elsewhere in
                # the draft, use that instead of the bare description.
                subject = coref_map.get(rel["subject"].lower(), rel["subject"])
                if subject.lower() not in title.lower():
                    title = f"{subject} {rel['verb']} — {title}"[:100]
                matched_subject = next((c for c in characters if c.lower() == subject.lower()
                                         or subject.lower() in c.lower() or c.lower() in subject.lower()), None)
                if matched_subject and matched_subject not in event_chars:
                    event_chars.insert(0, matched_subject)
            events.append({
                "title": title, "year": year,
                "category": _guess_event_category(sent),
                "description": sent[:400],
                "characters": event_chars[:5],
                "locations": event_locs[:3],
            })
            continue
        # Lore: expository/definitional narration, not something spoken aloud —
        # dialogue is nearly always in-scene action, not world-building.
        if sent.lstrip().startswith(('"', "'", "‘", "“")):
            continue
        is_lore = bool(LORE_SIGNAL_RE.search(sent))
        if not is_lore and DEFINITION_RE.search(sent):
            is_lore = any(re.search(r"\b" + re.escape(n.split()[0]) + r"\b", sent)
                          for n in (organizations + locations))
        if is_lore:
            named_org = next((o for o in organizations if o.split()[0].lower() in sent.lower()), None)
            named_loc = next((l for l in locations if l.split()[0].lower() in sent.lower()), None)
            category = "History" if named_org else ("Geography" if named_loc else "General")
            title_src = named_org or named_loc or " ".join(sent.split()[:6])
            lore.append({"title": title_src[:80], "category": category, "content": sent[:500]})

    return {
        "characters": characters[:20],
        "locations": locations[:12],
        "organizations": organizations[:8],
        "scenes": scenes[:30],
        "events": events[:15],
        "lore": lore[:10],
        "relations": relations,
        "character_relations": character_relations,
        "ner_available": ner["available"],
        "ner_note": ner["note"],
        "coref_available": coref_available,
        "coref_note": coref_note,
    }


def summarize_draft(text, entities):
    """A short extractive synopsis — opening sentences plus the principal cast
    and setting. No external model; this is meant to be edited, not final."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip().replace("\n", " "))
    opening = " ".join(s for s in sentences[:2] if s).strip()
    if len(opening) > 320:
        opening = opening[:317].rstrip() + "…"
    lead = entities["characters"][:3]
    setting = entities["locations"][:1]
    tail_bits = []
    if lead:
        tail_bits.append(f"Follows {', '.join(lead)}")
    if setting:
        tail_bits.append(f"set around {setting[0]}")
    tail = (" — " + " ".join(tail_bits) + ".") if tail_bits else ""
    return (opening + tail).strip() or "Draft imported — add a summary once you've reviewed the roster."


# --------------------------------------------------------------------------- #
#  Tier 3 — an opt-in Claude pass over the same draft, for the one thing
#  neither regex nor NER can do: actually read the passage. Resolving "the
#  old king" to a character named three paragraphs earlier, reasoning out a
#  year from "ten years after the founding," and telling a mischaracterized
#  scene from real lore all require comprehension, not classification. This
#  never runs automatically — it's a button in the review screen — and
#  degrades honestly the same way ContextCore's generate_answer() does: no
#  key or no package means a clear note, not a silent failure or a fake
#  result.
# --------------------------------------------------------------------------- #
DEEPEN_PROMPT = """You are helping a writer turn a draft into a structured story database. \
Below is the raw draft text, followed by a first-pass extraction produced by pattern matching \
and named-entity recognition. That first pass has no real reading comprehension: it can \
duplicate the same person under two names, miss which year a relative date resolves to, and \
misfile a scene as lore or vice versa.

Read the draft and return an IMPROVED version of the SAME structure:
- Merge any character, location, or organization that are actually the same entity under a \
different name or description (e.g. "the old king" naming a character introduced earlier) — \
only ones that actually appear in the first-pass extraction above, never a name you introduce \
yourself.
- "year" is an ABSOLUTE year in the story's OWN calendar (e.g. 1857, or 300 if the story counts \
in an era like "AE 300") — NEVER the bare number of years mentioned in a relative phrase. "ten \
years after the founding" is an equation, not a value: if the founding's own year is stated \
elsewhere in the text, ADD ten to it and return that sum as "year". If no absolute year appears \
anywhere in the text for you to add to, you cannot compute one — leave "year" null. Returning \
the number from the relative phrase itself (e.g. returning 10 for "a decade after") is wrong \
every time; null is the correct answer whenever you don't have a real anchor to compute from.
- Move anything miscategorized to where it actually belongs (an event that's really lore, a \
lore entry that's really scene narration).
- Do not invent people, places, or events that are not in the text or in the first-pass \
extraction above.
- "notes" must describe only changes you actually made in the JSON you're returning — never \
describe merging, dating, or moving something that isn't reflected in the data itself.

Respond with ONLY valid JSON (no markdown fences, no commentary), in exactly this shape:
{{"characters": ["Name", ...], "locations": ["Name", ...], "organizations": ["Name", ...],
  "events": [{{"title": "...", "year": <int or null>, "category": "war|death|birth|discovery|political|character", "description": "..."}}],
  "lore": [{{"title": "...", "category": "...", "content": "..."}}],
  "notes": "one sentence on what you changed and why"}}

Draft text:
{text}

First-pass extraction:
{preview_json}
"""


OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
# OpenRouter: one key, many backends — the model is an env var, not a code
# change, specifically so switching (Claude/DeepSeek/Qwen/whatever) later
# never needs touching this file again.
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-chat")


def _parse_deepen_json(raw):
    raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    return json.loads(raw)


def _call_openrouter(prompt):
    """Same shape as _call_ollama: raw HTTP via urllib, no new dependency.
    OpenRouter's API is OpenAI-compatible, so this is a chat/completions
    call with response_format constraining the output to JSON — the same
    guarantee Ollama's format='json' gives, for whichever backend model is
    actually selected. Returns (raw_text, error)."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None, "no OPENROUTER_API_KEY configured"
    body = json.dumps({
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }).encode()
    req = urllib.request.Request(OPENROUTER_URL, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
        return data["choices"][0]["message"]["content"], None
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode())
            msg = detail.get("error", {}).get("message", str(e))
        except Exception:
            msg = str(e)
        return None, f"OpenRouter returned {e.code}: {msg}"
    except urllib.error.URLError as e:
        return None, f"couldn't reach OpenRouter ({e})"
    except Exception as e:
        return None, f"OpenRouter call failed ({type(e).__name__}: {e})"


def _repair_deepen_output(data, preview):
    """A model correcting the first-pass extraction can rename or merge an
    entity, but it should never make one silently disappear — confirmed
    happening with Ollama specifically: tightening the prompt against
    inventing a year didn't just fix that, it also made the model drop a
    character and two whole events from its response with no merge or
    rename to explain it, just gone. A wrong value is something a reviewer
    can catch by reading it; a silently missing one usually isn't caught
    until much later. So: anything present in the original heuristic
    extraction that doesn't show up in the model's response, and doesn't
    look like it was merged into something that DOES appear (a same-or-
    substring name match, or an event whose original description is echoed
    in a returned one), gets added back exactly as it was."""
    for key in ("characters", "locations", "organizations"):
        original = preview.get(key, []) or []
        returned = data.get(key, []) or []
        returned_lower = [r.lower() for r in returned]
        for name in original:
            nl = name.lower()
            if nl in returned_lower or any(nl in r or r in nl for r in returned_lower):
                continue
            returned.append(name)
        data[key] = returned

    original_events = preview.get("events", []) or []
    returned_events = data.get("events", []) or []
    returned_desc = [(e.get("description") or "").strip().lower() for e in returned_events]
    for ev in original_events:
        d = (ev.get("description") or "").strip().lower()
        if d and d not in returned_desc:
            returned_events.append(ev)
    data["events"] = returned_events
    return data


def _call_ollama(prompt):
    """Raw HTTP call to a local Ollama server on this machine — urllib
    (already a dependency, via framevault_post) rather than a new package.
    format='json' asks Ollama's own grammar-constrained decoding to guarantee
    syntactically valid JSON, which the base model can't be trusted to do
    unprompted. Returns (raw_text, error)."""
    body = json.dumps({"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                        "format": "json"}).encode()
    req = urllib.request.Request(f"{OLLAMA_URL}/api/generate", data=body,
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode()).get("response", ""), None
    except urllib.error.URLError as e:
        return None, f"couldn't reach Ollama at {OLLAMA_URL} ({e})"
    except Exception as e:
        return None, f"Ollama call failed ({type(e).__name__}: {e})"


def deepen_draft(text, preview):
    """Returns (data, note). data is None when unavailable/failed — note
    explains why, mirroring generate_answer()'s honest-degradation pattern.
    Three backends, tried in order: a direct ANTHROPIC_API_KEY, then
    OpenRouter (one key, whichever model OPENROUTER_MODEL names — Claude,
    DeepSeek, Qwen, anything it hosts), then a local Ollama model as the
    last resort rather than skipping Tier 3 outright. Every backend only
    ever proposes — the writer reviews and commits like any other preview —
    which matters most for Ollama specifically: a small local model is far
    more likely to confidently invent an answer than to leave it alone, so
    only its note says to review closely; a real hosted model earns a plain
    "deepened with X" instead of a warning label."""
    preview_json = json.dumps({k: preview.get(k, []) for k in
                                ("characters", "locations", "organizations", "events", "lore")})
    prompt = DEEPEN_PROMPT.format(text=text[:8000], preview_json=preview_json)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(model=CLAUDE_MODEL, max_tokens=2000,
                                          messages=[{"role": "user", "content": prompt}])
            return _repair_deepen_output(_parse_deepen_json(msg.content[0].text), preview), None
        except ImportError:
            pass  # no anthropic package — fall through to OpenRouter/Ollama
        except Exception as e:  # billing, network, auth, malformed JSON
            return None, f"AI deepen failed ({type(e).__name__}: {e})."

    if os.environ.get("OPENROUTER_API_KEY"):
        raw, err = _call_openrouter(prompt)
        if err:
            return None, f"{err} — AI deepen skipped."
        try:
            data = _repair_deepen_output(_parse_deepen_json(raw), preview)
        except Exception:
            return None, f"OpenRouter ({OPENROUTER_MODEL}) responded but not with valid JSON — deepen skipped."
        data["notes"] = (
            f"Deepened via OpenRouter ({OPENROUTER_MODEL})."
            + (f" {data['notes']}" if data.get("notes") else "")
        )
        return data, None

    raw, err = _call_ollama(prompt)
    if err:
        reason = "No ANTHROPIC_API_KEY or OPENROUTER_API_KEY set, and " + err if not api_key else err
        return None, f"{reason} — AI deepen skipped."
    try:
        data = _parse_deepen_json(raw)
    except Exception:
        return None, f"Ollama ({OLLAMA_MODEL}) responded but not with valid JSON — deepen skipped."
    data = _repair_deepen_output(data, preview)
    data["notes"] = (
        f"Deepened locally with Ollama ({OLLAMA_MODEL}), not a hosted model — review this closely. "
        "A small local model is more likely to guess wrong on something like an unstated year "
        "than to leave it blank." + (f" Its own note: {data['notes']}" if data.get("notes") else "")
    )
    return data, None


# --------------------------------------------------------------------------- #
#  Auth — one login, borrowed from FrameVault (the identity seam)             #
# --------------------------------------------------------------------------- #
def framevault_post(path, payload, timeout=5):
    req = urllib.request.Request(
        f"{FRAMEVAULT_URL}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-Service-Key": SERVICE_KEY},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return False, json.loads(e.read().decode())
        except Exception:
            return False, {"error": f"FrameVault returned {e.code}"}
    except urllib.error.URLError:
        return False, {"error": "Couldn't reach FrameVault — is it running on port 5001?"}


def current_user():
    if "handle" not in session:
        return None
    return {"handle": session["handle"], "name": session.get("name", session["handle"]),
            "verified": session.get("verified", False)}


@app.context_processor
def inject_me():
    return {"me": current_user(), "framevault_url": FRAMEVAULT_URL}


# A page load with no session goes to /login; an /api/* call with no session
# gets a 401 instead of an HTML redirect (so the SPA's fetch() calls fail
# cleanly rather than parsing a login page as JSON). One hook instead of a
# decorator on every route, so a future route can't accidentally ship ungated.
PUBLIC_PATHS = {"/login", "/logout", "/__whoami"}


@app.before_request
def require_login():
    if request.path in PUBLIC_PATHS or request.path.startswith("/static/"):
        return None
    if "handle" in session:
        return None
    if request.path.startswith("/api/"):
        return jsonify(ok=False, error="Please log in with your FrameVault account."), 401
    return redirect(url_for("login", next=request.path))


def credit_framevault(handle, universe_name):
    """THE MAGIC MOMENT: publishing a canon becomes verified portfolio history on FrameVault."""
    return framevault_post("/api/credit", {
        "handle": handle,
        "kind": "canon.published",
        "source": "Story Atlas",
        "weight": 3,
        "review": {
            "author_name": "Story Atlas", "rating": 5,
            "body": f"Published the canon for “{universe_name}”.",
            "context": f"Published “{universe_name}” · via Story Atlas",
        },
    })


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        handle = (request.form.get("handle") or "").strip().lstrip("@").lower()
        password = request.form.get("password") or ""
        ok, data = framevault_post("/api/authenticate", {"handle": handle, "password": password})
        if not ok:
            return render_template("login.html", error=data.get("error", "Login failed.")), 401
        u = data["user"]
        session["handle"] = u["handle"]
        session["name"] = u["display_name"]
        session["verified"] = u["verified"]
        return redirect(request.args.get("next") or url_for("index"))
    if "handle" in session:
        return redirect(url_for("index"))
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --------------------------------------------------------------------------- #
#  Web                                                                         #
# --------------------------------------------------------------------------- #
@app.get("/")
def index():
    return render_template("index.html")


@app.get("/__whoami")
def whoami():
    """Identity probe for scripts/check_ports.py — a port can be identified, not guessed."""
    return jsonify(app="Story Atlas", track="CreativeOS",
                   role="creative intelligence workspace", port=PORT)


# --------------------------------------------------------------------------- #
#  JSON API                                                                    #
# --------------------------------------------------------------------------- #
@app.get("/api/universes")
def api_universes():
    return jsonify(rows("SELECT * FROM universes ORDER BY id"))


@app.post("/api/universes")
def api_create_universe():
    d = request.get_json(force=True)
    name = (d.get("name") or "").strip()
    if not name:
        return jsonify(error="Name is required"), 400
    db = get_db()
    uid = db.execute(
        "INSERT INTO universes(name, genre, summary, era_label, created_at) VALUES(?,?,?,?,?)",
        (name, d.get("genre", ""), d.get("summary", ""), d.get("era_label", "Year"), now()),
    ).lastrowid
    db.commit()
    return jsonify(one("SELECT * FROM universes WHERE id=?", (uid,))), 201


@app.delete("/api/universes/<int:uid>")
def api_delete_universe(uid):
    if not one("SELECT id FROM universes WHERE id=?", (uid,)):
        return jsonify(error="Not found"), 404
    db = get_db()
    db.execute("DELETE FROM universes WHERE id=?", (uid,))  # cascades to every child table
    db.commit()
    return jsonify(ok=True)


@app.get("/api/universes/<int:uid>/overview")
def api_overview(uid):
    u = one("SELECT * FROM universes WHERE id=?", (uid,))
    if not u:
        return jsonify(error="Not found"), 404
    counts = {
        "characters": one("SELECT COUNT(*) n FROM characters WHERE universe_id=?", (uid,))["n"],
        "locations": one("SELECT COUNT(*) n FROM locations WHERE universe_id=?", (uid,))["n"],
        "organizations": one("SELECT COUNT(*) n FROM organizations WHERE universe_id=?", (uid,))["n"],
        "events": one("SELECT COUNT(*) n FROM events WHERE universe_id=?", (uid,))["n"],
        "scenes": one("SELECT COUNT(*) n FROM scenes WHERE universe_id=?", (uid,))["n"],
        "lore": one("SELECT COUNT(*) n FROM lore WHERE universe_id=?", (uid,))["n"],
        "relationships": one("SELECT COUNT(*) n FROM relationships WHERE universe_id=?", (uid,))["n"],
    }
    warns = canon_check(uid)
    span = one("SELECT MIN(year) lo, MAX(year) hi FROM events WHERE universe_id=? AND year IS NOT NULL", (uid,))
    recent = rows("SELECT id,name,'character' AS kind FROM characters WHERE universe_id=? ORDER BY id DESC LIMIT 5", (uid,))
    key_events = rows("SELECT * FROM events WHERE universe_id=? AND year IS NOT NULL ORDER BY year DESC LIMIT 5", (uid,))
    return jsonify(universe=u, counts=counts, span=span,
                   warnings=warns, warning_count=len(warns),
                   recent=recent, key_events=key_events)


@app.post("/api/universes/<int:uid>/publish")
def api_publish_universe(uid):
    """THE MAGIC MOMENT: publishing writes a verified `canon.published` credit to FrameVault."""
    u = one("SELECT * FROM universes WHERE id=?", (uid,))
    if not u:
        return jsonify(ok=False, error="Not found"), 404
    if u["published_at"]:
        return jsonify(ok=False, error="Already published."), 409
    me = current_user()
    db = get_db()
    db.execute("UPDATE universes SET published_at=?, published_by=? WHERE id=?",
               (now(), me["handle"], uid))
    ok, detail = credit_framevault(me["handle"], u["name"])
    resp = {"ok": True, "credited": ok}
    resp["note"] = ("Credit written to FrameVault." if ok
                     else f"FrameVault not updated: {detail.get('error', 'error')}")
    if ok:
        resp["public_url"] = f"{FRAMEVAULT_URL}/@{me['handle']}"
    db.commit()
    return jsonify(resp)


@app.get("/api/universes/<int:uid>/characters")
def api_characters(uid):
    cs = rows("SELECT * FROM characters WHERE universe_id=? ORDER BY name", (uid,))
    return jsonify(cs)


@app.get("/api/characters/<int:cid>")
def api_character(cid):
    c = one("SELECT * FROM characters WHERE id=?", (cid,))
    if not c:
        return jsonify(error="Not found"), 404
    c["relationships"] = relations_of(c["universe_id"], "character", cid)
    c["scenes"] = scenes_with_character(c["universe_id"], cid)
    return jsonify(c)


CHAR_FIELDS = ("name role age appearance biography personality goals motivations "
               "fears conflicts arc status birth_year death_year").split()


@app.post("/api/universes/<int:uid>/characters")
def api_create_character(uid):
    d = request.get_json(force=True)
    if not (d.get("name") or "").strip():
        return jsonify(error="Name is required"), 400
    vals = []
    for f in CHAR_FIELDS:
        v = d.get(f)
        if f in ("birth_year", "death_year"):
            # Year columns stay NULL when blank — never coerce to "" (breaks canon math).
            vals.append(int(v) if str(v).strip().lstrip("-").isdigit() else None)
        elif f == "status":
            vals.append(v or "alive")
        else:
            vals.append(v if v is not None else "")
    db = get_db()
    cid = db.execute(
        f"INSERT INTO characters(universe_id,{','.join(CHAR_FIELDS)},created_at) "
        f"VALUES(?,{','.join('?'*len(CHAR_FIELDS))},?)", (uid, *vals, now())).lastrowid
    db.commit()
    return jsonify(one("SELECT * FROM characters WHERE id=?", (cid,))), 201


@app.put("/api/characters/<int:cid>")
def api_update_character(cid):
    d = request.get_json(force=True)
    sets, vals = [], []
    for f in CHAR_FIELDS:
        if f in d:
            v = d[f]
            if f in ("birth_year", "death_year"):
                v = int(v) if str(v).strip().lstrip("-").isdigit() else None
            sets.append(f"{f}=?")
            vals.append(v)
    if not sets:
        return jsonify(error="Nothing to update"), 400
    db = get_db()
    db.execute(f"UPDATE characters SET {','.join(sets)} WHERE id=?", (*vals, cid))
    db.commit()
    return jsonify(one("SELECT * FROM characters WHERE id=?", (cid,)))


@app.delete("/api/characters/<int:cid>")
def api_delete_character(cid):
    if not one("SELECT id FROM characters WHERE id=?", (cid,)):
        return jsonify(error="Not found"), 404
    db = get_db()
    db.execute("DELETE FROM characters WHERE id=?", (cid,))  # scene_characters cascades
    db.commit()
    return jsonify(ok=True)


@app.post("/api/characters/<int:cid>/canon-preview")
def api_character_canon_preview(cid):
    """Canon Engine impact preview: apply a hypothetical field change, see which
    warnings it would add/resolve, then roll back — nothing is ever persisted.
    Reuses canon_check() verbatim by applying the edit inside the same request's
    uncommitted transaction (canon_check() reads through the same g.db
    connection, so it sees the pending write) and rolling back before returning."""
    row = one("SELECT universe_id FROM characters WHERE id=?", (cid,))
    if not row:
        return jsonify(error="Not found"), 404
    uid = row["universe_id"]
    d = request.get_json(force=True)
    sets, vals = [], []
    for f in CHAR_FIELDS:
        if f in d:
            v = d[f]
            if f in ("birth_year", "death_year"):
                v = int(v) if str(v).strip().lstrip("-").isdigit() else None
            sets.append(f"{f}=?")
            vals.append(v)
    if not sets:
        return jsonify(error="Nothing to preview"), 400

    db = get_db()
    before = canon_check(uid)
    db.execute(f"UPDATE characters SET {','.join(sets)} WHERE id=?", (*vals, cid))
    after = canon_check(uid)
    db.rollback()

    def key(w):
        return (w["kind"], w["message"])
    before_keys = {key(w) for w in before}
    after_keys = {key(w) for w in after}
    new_warnings = [w for w in after if key(w) not in before_keys]
    resolved_warnings = [w for w in before if key(w) not in after_keys]
    return jsonify(
        before_count=len(before), after_count=len(after),
        new_warnings=new_warnings, resolved_warnings=resolved_warnings,
        unchanged_count=len(after) - len(new_warnings),
    )


@app.get("/api/universes/<int:uid>/timeline")
def api_timeline(uid):
    evs = rows("SELECT * FROM events WHERE universe_id=? ORDER BY year, id", (uid,))
    for e in evs:
        e["links"] = relations_of(uid, "event", e["id"])
    u = one("SELECT * FROM universes WHERE id=?", (uid,))
    return jsonify(events=evs, era_label=(u["era_label"] if u else "Year"))


@app.post("/api/universes/<int:uid>/events")
def api_create_event(uid):
    d = request.get_json(force=True)
    if not (d.get("title") or "").strip():
        return jsonify(error="Title is required"), 400
    yr = d.get("year")
    yr = int(yr) if str(yr).strip().lstrip("-").isdigit() else None
    db = get_db()
    eid = db.execute(
        "INSERT INTO events(universe_id,title,year,category,description) VALUES(?,?,?,?,?)",
        (uid, d["title"], yr, d.get("category", ""), d.get("description", ""))).lastrowid
    db.commit()
    return jsonify(one("SELECT * FROM events WHERE id=?", (eid,))), 201


@app.delete("/api/events/<int:eid>")
def api_delete_event(eid):
    if not one("SELECT id FROM events WHERE id=?", (eid,)):
        return jsonify(error="Not found"), 404
    db = get_db()
    db.execute("DELETE FROM events WHERE id=?", (eid,))
    db.commit()
    return jsonify(ok=True)


@app.get("/api/universes/<int:uid>/locations")
def api_locations(uid):
    return jsonify(rows("SELECT * FROM locations WHERE universe_id=? ORDER BY name", (uid,)))


@app.delete("/api/locations/<int:lid>")
def api_delete_location(lid):
    if not one("SELECT id FROM locations WHERE id=?", (lid,)):
        return jsonify(error="Not found"), 404
    db = get_db()
    db.execute("DELETE FROM locations WHERE id=?", (lid,))  # scenes.location_id -> SET NULL
    db.commit()
    return jsonify(ok=True)


@app.get("/api/universes/<int:uid>/organizations")
def api_organizations(uid):
    os_ = rows("SELECT * FROM organizations WHERE universe_id=? ORDER BY name", (uid,))
    for o in os_:
        lead = o["leadership"]
        o["leader_name"] = entity_label("character", int(lead)) if lead.isdigit() else lead
    return jsonify(os_)


@app.delete("/api/organizations/<int:oid>")
def api_delete_organization(oid):
    if not one("SELECT id FROM organizations WHERE id=?", (oid,)):
        return jsonify(error="Not found"), 404
    db = get_db()
    db.execute("DELETE FROM organizations WHERE id=?", (oid,))
    db.commit()
    return jsonify(ok=True)


@app.get("/api/universes/<int:uid>/scenes")
def api_scenes(uid):
    sc = rows("SELECT s.*, l.name AS location_name FROM scenes s "
              "LEFT JOIN locations l ON l.id=s.location_id WHERE s.universe_id=? "
              "ORDER BY s.time_year, s.id", (uid,))
    for s in sc:
        s["characters"] = rows(
            "SELECT c.id, c.name FROM characters c JOIN scene_characters sc ON sc.character_id=c.id "
            "WHERE sc.scene_id=?", (s["id"],))
    return jsonify(sc)


@app.delete("/api/scenes/<int:sid>")
def api_delete_scene(sid):
    if not one("SELECT id FROM scenes WHERE id=?", (sid,)):
        return jsonify(error="Not found"), 404
    db = get_db()
    db.execute("DELETE FROM scenes WHERE id=?", (sid,))  # scene_characters cascades
    db.commit()
    return jsonify(ok=True)


@app.get("/api/universes/<int:uid>/lore")
def api_lore(uid):
    return jsonify(rows("SELECT * FROM lore WHERE universe_id=? ORDER BY category, title", (uid,)))


@app.delete("/api/lore/<int:lid>")
def api_delete_lore(lid):
    if not one("SELECT id FROM lore WHERE id=?", (lid,)):
        return jsonify(error="Not found"), 404
    db = get_db()
    db.execute("DELETE FROM lore WHERE id=?", (lid,))
    db.commit()
    return jsonify(ok=True)


def _existing_flagged(uid, names, table):
    existing = {r["name"].lower() for r in rows(f"SELECT name FROM {table} WHERE universe_id=?", (uid,))}
    return [{"name": n, "existing": n.lower() in existing} for n in names]


@app.get("/api/universes/<int:uid>/drafts")
def api_list_drafts(uid):
    """So a past draft can be reopened and edited instead of only ever being
    a one-shot import — the text was always kept in the drafts table for
    provenance, but nothing ever read it back until now."""
    ds = rows("SELECT id, content, summary, created_at FROM drafts WHERE universe_id=? "
              "ORDER BY created_at DESC", (uid,))
    for d in ds:
        d["preview"] = (d["content"][:160] + "…") if len(d["content"]) > 160 else d["content"]
        del d["content"]
    return jsonify(ds)


@app.get("/api/drafts/<int:did>")
def api_get_draft(did):
    d = one("SELECT * FROM drafts WHERE id=?", (did,))
    if not d:
        return jsonify(error="Not found"), 404
    return jsonify(d)


@app.post("/api/universes/<int:uid>/draft/extract")
def api_draft_extract(uid):
    """Preview only — proposes candidates from pasted text, writes nothing."""
    if not one("SELECT id FROM universes WHERE id=?", (uid,)):
        return jsonify(error="Not found"), 404
    d = request.get_json(force=True)
    text = (d.get("text") or "").strip()
    if not text:
        return jsonify(error="Paste some draft text first"), 400
    u = one("SELECT era_label FROM universes WHERE id=?", (uid,))
    entities = extract_entities(text, era_label=(u["era_label"] if u else "Year"))
    summary = summarize_draft(text, entities)
    return jsonify(
        characters=_existing_flagged(uid, entities["characters"], "characters"),
        locations=_existing_flagged(uid, entities["locations"], "locations"),
        organizations=_existing_flagged(uid, entities["organizations"], "organizations"),
        scenes=entities["scenes"],
        events=entities["events"],
        lore=entities["lore"],
        character_relations=entities["character_relations"],
        summary=summary,
        ner_available=entities["ner_available"],
        ner_note=entities["ner_note"],
        coref_available=entities["coref_available"],
        coref_note=entities["coref_note"],
    )


@app.post("/api/universes/<int:uid>/draft/deepen")
def api_draft_deepen(uid):
    """Tier 3, opt-in: re-reads the draft with Claude to fix what pattern
    matching and NER structurally can't — coreference, relative-date
    reasoning, miscategorized entries. Never writes to the database; the
    writer still reviews and commits like any other preview."""
    if not one("SELECT id FROM universes WHERE id=?", (uid,)):
        return jsonify(error="Not found"), 404
    d = request.get_json(force=True)
    text = (d.get("text") or "").strip()
    if not text:
        return jsonify(error="No draft text to deepen"), 400
    data, note = deepen_draft(text, d.get("preview") or {})
    if data is None:
        return jsonify(available=False, note=note)
    return jsonify(
        available=True,
        note=data.get("notes"),
        characters=_existing_flagged(uid, data.get("characters", []), "characters"),
        locations=_existing_flagged(uid, data.get("locations", []), "locations"),
        organizations=_existing_flagged(uid, data.get("organizations", []), "organizations"),
        events=data.get("events", []),
        lore=data.get("lore", []),
    )


@app.post("/api/universes/<int:uid>/draft/commit")
def api_draft_commit(uid):
    """Writes the (writer-reviewed) candidate roster: new characters/locations/
    organizations, one scene per chunk with its present characters, a verb-
    typed relationship wherever the draft's own dependency parse resolved one
    between two known characters, a generic linked edge for the rest who
    merely share a scene, an event->character/location relationship for
    whoever and wherever each timeline event actually names, a death/birth
    event updating that character's own status/birth_year/death_year (only
    when it isn't already set — never overwriting a hand-corrected record),
    and refreshes the universe summary. Existing records with a matching
    name are reused, not duplicated."""
    if not one("SELECT id FROM universes WHERE id=?", (uid,)):
        return jsonify(error="Not found"), 404
    d = request.get_json(force=True)
    db = get_db()
    ts = now()
    new_links = 0

    name_to_id, new_chars = {}, 0
    for name in d.get("characters", []):
        name = _sanitize_name(name)
        if not name:
            continue
        existing = one("SELECT id FROM characters WHERE universe_id=? AND lower(name)=?", (uid, name.lower()))
        if existing:
            name_to_id[name.lower()] = existing["id"]
            continue
        cid = db.execute(
            "INSERT INTO characters(universe_id,name,role,age,appearance,biography,personality,goals,"
            "motivations,fears,conflicts,arc,status,birth_year,death_year,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (uid, name, "", "", "", "", "", "", "", "", "", "", "alive", None, None, ts)).lastrowid
        name_to_id[name.lower()] = cid
        new_chars += 1

    loc_name_to_id, new_locs = {}, 0
    for name in d.get("locations", []):
        name = _sanitize_name(name)
        if not name:
            continue
        existing = one("SELECT id FROM locations WHERE universe_id=? AND lower(name)=?", (uid, name.lower()))
        if existing:
            loc_name_to_id[name.lower()] = existing["id"]
            continue
        lid = db.execute("INSERT INTO locations(universe_id,name,kind,description,history,population) "
                          "VALUES(?,?,?,?,?,?)", (uid, name, "", "", "", "")).lastrowid
        loc_name_to_id[name.lower()] = lid
        new_locs += 1

    new_orgs = 0
    for name in d.get("organizations", []):
        name = _sanitize_name(name)
        if not name or one("SELECT id FROM organizations WHERE universe_id=? AND lower(name)=?", (uid, name.lower())):
            continue
        db.execute("INSERT INTO organizations(universe_id,name,kind,leadership,goals,history) "
                   "VALUES(?,?,?,?,?,?)", (uid, name, "", "", "", ""))
        new_orgs += 1

    scene_ids = []
    for sc in d.get("scenes", []):
        title = (sc.get("title") or "Untitled scene").strip()[:120]
        # Matched by title so re-importing an edited draft (same opening
        # sentence for an unchanged scene) reuses the existing row instead of
        # piling up a duplicate — the same "existing records are reused"
        # rule characters/locations/organizations already follow.
        existing_scene = one("SELECT id FROM scenes WHERE universe_id=? AND title=?", (uid, title))
        sid = existing_scene["id"] if existing_scene else db.execute(
            "INSERT INTO scenes(universe_id,title,location_id,time_year,purpose,conflict,info) "
            "VALUES(?,?,?,?,?,?,?)", (uid, title, None, None, "", "", (sc.get("text") or "")[:1000])).lastrowid
        for cname in sc.get("characters", []):
            cid = name_to_id.get((cname or "").strip().lower())
            if cid:
                db.execute("INSERT OR IGNORE INTO scene_characters(scene_id,character_id) VALUES(?,?)", (sid, cid))
        scene_ids.append(sid)

    # Typed character-to-character relations from the actual verb ("gave",
    # "betrayed", "married"), extracted alongside event detection. Runs
    # BEFORE the co-occurrence pass below, on purpose: that pass only adds
    # its generic 'linked' edge when no relationship exists yet for a pair,
    # so a specific tie created here always wins over the generic fallback
    # for the same two people, instead of both existing at once.
    for cr in d.get("character_relations", []):
        sid = name_to_id.get((cr.get("subject") or "").strip().lower())
        tid = name_to_id.get((cr.get("object") or "").strip().lower())
        verb = (cr.get("verb") or "").strip()
        if not (sid and tid and verb) or sid == tid:
            continue
        exists = one(
            "SELECT id FROM relationships WHERE universe_id=? AND source_type='character' AND "
            "target_type='character' AND ((source_id=? AND target_id=?) OR (source_id=? AND target_id=?))",
            (uid, sid, tid, tid, sid))
        if not exists:
            db.execute(
                "INSERT INTO relationships(universe_id,source_type,source_id,target_type,target_id,kind,label) "
                "VALUES(?, 'character', ?, 'character', ?, ?, ?)",
                (uid, sid, tid, verb, f"'{verb}' in the draft"))
            new_links += 1

    # Co-occurrence: characters who share a scene get one linked edge each.
    added_pairs = set()
    for sc in d.get("scenes", []):
        present = [name_to_id.get((c or "").strip().lower()) for c in sc.get("characters", [])]
        present = [p for p in present if p]
        for i in range(len(present)):
            for j in range(i + 1, len(present)):
                key = tuple(sorted((present[i], present[j])))
                if key in added_pairs:
                    continue
                added_pairs.add(key)
                exists = one(
                    "SELECT id FROM relationships WHERE universe_id=? AND source_type='character' AND "
                    "target_type='character' AND ((source_id=? AND target_id=?) OR (source_id=? AND target_id=?))",
                    (uid, key[0], key[1], key[1], key[0]))
                if not exists:
                    db.execute(
                        "INSERT INTO relationships(universe_id,source_type,source_id,target_type,target_id,kind,label) "
                        "VALUES(?, 'character', ?, 'character', ?, 'linked', 'appears together in the draft')",
                        (uid, key[0], key[1]))

    new_events = 0
    for ev in d.get("events", []):
        title = _sanitize_name(ev.get("title"))
        if not title:
            continue
        year, category = ev.get("year"), ev.get("category") or ""
        # Matched by title, same reuse-not-duplicate rule as scenes above —
        # this is what makes re-importing an edited draft additive instead of
        # doubling up every event that didn't change.
        existing_event = one("SELECT id FROM events WHERE universe_id=? AND title=?", (uid, title[:200]))
        if existing_event:
            eid = existing_event["id"]
        else:
            eid = db.execute("INSERT INTO events(universe_id,title,year,category,description) VALUES(?,?,?,?,?)",
                              (uid, title[:200], year, category, ev.get("description") or "")).lastrowid
            new_events += 1

        # Reconcile the event with the people and places it actually names —
        # this is the piece that was missing: extraction already worked out
        # which characters/locations a sentence involves, but nothing carried
        # that into a real relationship row, so every draft-imported event
        # used to land with no connections at all.
        event_cids = []
        for cname in ev.get("characters", []):
            cid = name_to_id.get((cname or "").strip().lower())
            if cid and cid not in event_cids:
                event_cids.append(cid)
                db.execute(
                    "INSERT INTO relationships(universe_id,source_type,source_id,target_type,target_id,kind,label) "
                    "VALUES(?, 'event', ?, 'character', ?, 'mentions', ?)",
                    (uid, eid, cid, category or "involves"))
                new_links += 1
        for lname in ev.get("locations", []):
            lid = loc_name_to_id.get((lname or "").strip().lower())
            if lid:
                db.execute(
                    "INSERT INTO relationships(universe_id,source_type,source_id,target_type,target_id,kind,label) "
                    "VALUES(?, 'event', ?, 'location', ?, 'mentions', ?)",
                    (uid, eid, lid, category or "involves"))
                new_links += 1

        # A death or birth event with a resolved subject is exactly the fact
        # that should update the character's own lifecycle fields — never
        # touching a value that's already set, so a hand-corrected record is
        # never silently overwritten by a re-import.
        if event_cids:
            primary = event_cids[0]
            if category == "death":
                row = one("SELECT death_year, status FROM characters WHERE id=?", (primary,))
                if row and row["death_year"] is None and row["status"] != "dead":
                    if year is not None:
                        db.execute("UPDATE characters SET status='dead', death_year=? WHERE id=?", (year, primary))
                    else:
                        db.execute("UPDATE characters SET status='dead' WHERE id=?", (primary,))
            elif category == "birth" and year is not None:
                row = one("SELECT birth_year FROM characters WHERE id=?", (primary,))
                if row and row["birth_year"] is None:
                    db.execute("UPDATE characters SET birth_year=? WHERE id=?", (year, primary))

    new_lore = 0
    for lo in d.get("lore", []):
        title = _sanitize_name(lo.get("title"))
        if not title:
            continue
        db.execute("INSERT INTO lore(universe_id,title,category,content) VALUES(?,?,?,?)",
                   (uid, title[:200], lo.get("category") or "General", lo.get("content") or ""))
        new_lore += 1

    summary = (d.get("summary") or "").strip()
    if summary:
        db.execute("UPDATE universes SET summary=? WHERE id=?", (summary, uid))

    text = d.get("text") or ""
    if text.strip():
        db.execute("INSERT INTO drafts(universe_id, content, summary, created_at) VALUES(?,?,?,?)",
                   (uid, text, summary, ts))

    db.commit()
    return jsonify(characters_created=new_chars, locations_created=new_locs,
                   organizations_created=new_orgs, scenes_created=len(scene_ids),
                   events_created=new_events, lore_created=new_lore,
                   links_created=new_links), 201


@app.get("/api/universes/<int:uid>/graph")
def api_graph(uid):
    nodes, edges = [], []
    palette = {"character": "character", "location": "location",
               "organization": "organization", "event": "event"}
    for c in rows("SELECT id,name,status FROM characters WHERE universe_id=?", (uid,)):
        nodes.append({"id": f"character-{c['id']}", "type": "character",
                      "label": c["name"], "dead": c["status"] == "dead"})
    for l in rows("SELECT id,name FROM locations WHERE universe_id=?", (uid,)):
        nodes.append({"id": f"location-{l['id']}", "type": "location", "label": l["name"]})
    for o in rows("SELECT id,name FROM organizations WHERE universe_id=?", (uid,)):
        nodes.append({"id": f"organization-{o['id']}", "type": "organization", "label": o["name"]})
    for e in rows("SELECT id,title FROM events WHERE universe_id=?", (uid,)):
        nodes.append({"id": f"event-{e['id']}", "type": "event", "label": e["title"]})
    node_ids = {n["id"] for n in nodes}
    for r in rows("SELECT * FROM relationships WHERE universe_id=?", (uid,)):
        s = f"{r['source_type']}-{r['source_id']}"
        t = f"{r['target_type']}-{r['target_id']}"
        if s in node_ids and t in node_ids:
            edges.append({"source": s, "target": t, "kind": r["kind"], "label": r["label"]})
    return jsonify(nodes=nodes, edges=edges)


@app.get("/api/universes/<int:uid>/graph/centrality")
def api_graph_centrality(uid):
    result = graph_centrality(uid)
    if result is None:
        return jsonify(available=False, note="networkx isn't installed — centrality unavailable.")
    return jsonify(available=True, characters=result)


@app.get("/api/universes/<int:uid>/narrative-state")
def api_narrative_state(uid):
    as_of = request.args.get("as_of")
    as_of_year = int(as_of) if as_of and as_of.lstrip("-").isdigit() else None
    return jsonify(narrative_state(uid, as_of_year))


@app.get("/api/universes/<int:uid>/canon")
def api_canon(uid):
    return jsonify(warnings=canon_check(uid))


@app.post("/api/universes/<int:uid>/ask")
def api_ask(uid):
    d = request.get_json(force=True)
    q = (d.get("q") or "").strip()
    if not q:
        return jsonify(error="Ask a question"), 400
    return jsonify(ai_answer(uid, q))


@app.get("/api/universes/<int:uid>/search")
def api_search(uid):
    """Read-only search across every entity type in this universe, for the
    command palette. Additive endpoint — doesn't touch any existing route."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 1:
        return jsonify(results=[])
    like = f"%{q}%"
    db = get_db()
    results = []
    for c in db.execute(
        "SELECT id, name, role FROM characters WHERE universe_id=? AND name LIKE ? LIMIT 6", (uid, like)
    ).fetchall():
        results.append({"type": "Character", "title": c["name"], "subtitle": c["role"], "view": "characters", "id": c["id"]})
    for l in db.execute(
        "SELECT id, name, kind FROM locations WHERE universe_id=? AND name LIKE ? LIMIT 6", (uid, like)
    ).fetchall():
        results.append({"type": "Location", "title": l["name"], "subtitle": l["kind"], "view": "locations", "id": l["id"]})
    for o in db.execute(
        "SELECT id, name, kind FROM organizations WHERE universe_id=? AND name LIKE ? LIMIT 6", (uid, like)
    ).fetchall():
        results.append({"type": "Organization", "title": o["name"], "subtitle": o["kind"], "view": "organizations", "id": o["id"]})
    for e in db.execute(
        "SELECT id, title, year FROM events WHERE universe_id=? AND title LIKE ? LIMIT 6", (uid, like)
    ).fetchall():
        results.append({"type": "Event", "title": e["title"],
                         "subtitle": f"AE {e['year']}" if e["year"] is not None else "", "view": "timeline", "id": e["id"]})
    for s in db.execute(
        "SELECT id, title FROM scenes WHERE universe_id=? AND title LIKE ? LIMIT 6", (uid, like)
    ).fetchall():
        results.append({"type": "Scene", "title": s["title"], "subtitle": "", "view": "scenes", "id": s["id"]})
    for lo in db.execute(
        "SELECT id, title, category FROM lore WHERE universe_id=? AND title LIKE ? LIMIT 6", (uid, like)
    ).fetchall():
        results.append({"type": "Lore", "title": lo["title"], "subtitle": lo["category"], "view": "lore", "id": lo["id"]})
    return jsonify(results=results)


if __name__ == "__main__":
    # Windows consoles default to cp1252, which cannot encode the em dash/arrow
    # used in the banner. Force UTF-8 where the stream supports it.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    init_db()
    print("  Story Atlas - creative intelligence workspace")
    print(f"  -> http://127.0.0.1:{PORT}\n")
    # threaded=True matters here specifically because of Ollama: a deepen
    # call can take 30-90+ seconds, and a single-threaded dev server would
    # block every other request (including just clicking around elsewhere
    # in the app) until it finishes — which reads exactly like the app
    # having frozen or "not working," not like a slow request in flight.
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=PORT, debug=DEBUG, threaded=True)
