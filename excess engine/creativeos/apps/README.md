# CreativeOS applications

Each application owns its **domain** engines and lives in its own folder. They
all share one platform — `../src/creativeos_engine/` — and none of them imports
another.

```
creativeos/
  src/creativeos_engine/     THE SHARED PLATFORM — 14 engines, one graph,
                             one event log, one identity. Knows no domain.
  apps/
    storyatlas/              Story · World · Character · Canon · Timeline
    framevault/              Provenance · Reputation
    filmcrew/                Production · Casting · Contracts
    demo_wiring.py           FilmCrew ↔ FrameVault, talking through events
```

## The rule that keeps it coherent

**Shared engines stay shared; domain engines stay in their app; applications
never import each other.**

- **Vertical is allowed.** Every app depends on `creativeos_engine` — the graph,
  the event bus, identity, verification. That is the point of a platform.
- **Horizontal is forbidden.** FilmCrew must not import FrameVault. When they
  need to communicate they publish and subscribe.

That second rule is enforced by a test, not by discipline:
`filmcrew/tests/test_wiring.py::test_filmcrew_imports_nothing_from_any_sibling_application`
parses FilmCrew's imports and fails if a sibling appears. It checks the parsed
imports rather than the file's text, because the module's own comments name
FrameVault while explaining the boundary — and a text scan would fail on the
very sentence describing the rule.

## What connects them

Nothing, directly. They share the platform's event log, and that is all.

```
FilmCrew                          FrameVault
   │                                  │
   │  publishes "hire.completed"      │  subscribes to it
   └──────────►  CreativeOS bus  ◄────┘
```

FilmCrew holds no URL, no service key and no reference to FrameVault. It does
not know whether anyone is listening. Run `python demo_wiring.py` to watch a
production go from draft to paid and a creator's reputation change as a result,
with the full event log printed at the end.

**Why this matters:** the apps in `companies/creativeos/` currently do the same
job with a direct HTTP POST from FilmCrew to FrameVault's `/api/credit`. That
means FilmCrew must know FrameVault's address, its key, and whether it is
running — and if FrameVault is down, paying a contract breaks. Constitution
v2.0 forbids exactly this: *"Applications communicate only through events. No
tight coupling."*

## Two domain rules worth knowing

**Credit fires on `paid`, not on `hired`** (FilmCrew). An offer can be withdrawn
and a shoot can collapse; money changing hands is the first moment the work is
evidenced. Every intermediate state is announced but credits nobody.

**Reputation is earned, never claimed** (FrameVault). A credit is something
another application *witnessed*. There is deliberately no method to assert one
about yourself — a résumé is a claim, a paid contract is evidence, and a back
door for the first would quietly turn this back into a résumé.

## Running them

```bash
cd storyatlas  && python -m pytest -q      # 162
cd framevault  && python -m pytest -q      #  24
cd filmcrew    && python -m pytest -q      #  14
python apps/demo_wiring.py
```

Each app carries its own `conftest.py`, which finds the shared platform by
**searching upward** for `src/creativeos_engine` rather than counting parent
directories. A fixed depth broke silently the moment StoryAtlas moved under
`creativeos/` — and a skipped test module looks exactly like a passing one.
