"""Every demo actually runs.

Written because two of them silently stopped running and every other test still
passed. Moving `money` up into the platform broke `rightsforge/demo.py` and
`creatorstack/demo.py` on import, and nothing noticed — the conftest puts the
platform on `sys.path` for tests, and a demo is a standalone script that gets
none of that.

A demo is the first thing anyone runs and the only part of an engine most people
will ever look at. One that raises on import is worse than no demo, because it
says the whole thing is broken.

Run as subprocesses rather than imported: these are scripts with top-level side
effects, and importing them would execute in this process, share `sys.path` with
the tests, and hide the exact failure this exists to catch.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: Every demo under the CreativeOS tree, discovered rather than listed — a
#: hand-maintained list would miss the next engine, which is precisely when this
#: test stops earning its keep.
DEMOS = sorted(p for p in ROOT.rglob("demo*.py") if "__pycache__" not in p.parts)


def test_there_are_demos_to_check():
    """Guards against the glob quietly matching nothing after a move."""
    assert DEMOS, f"no demo scripts found under {ROOT}"


@pytest.mark.parametrize("demo", DEMOS, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_a_demo_runs_cleanly(demo):
    result = subprocess.run(
        [sys.executable, str(demo)],
        cwd=str(demo.parent), capture_output=True, text=True, timeout=300,
        encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, (
        f"{demo.name} exited {result.returncode}\n"
        f"--- stderr ---\n{(result.stderr or '')[-2000:]}")
    assert result.stdout.strip(), f"{demo.name} printed nothing"
