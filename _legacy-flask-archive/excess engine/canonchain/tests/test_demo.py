"""The demo runs.

Its own test because Canonchain sits outside the CreativeOS tree and so is not
covered by `creativeos/tests/test_demos.py`. The reason that test exists applies
here too: a demo is the first thing anyone runs, and one that raises on import
says the whole engine is broken.
"""

import subprocess
import sys
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1] / "demo.py"


def test_the_demo_runs_cleanly():
    result = subprocess.run(
        [sys.executable, str(DEMO)], cwd=str(DEMO.parent),
        capture_output=True, text=True, timeout=120,
        encoding="utf-8", errors="replace")
    assert result.returncode == 0, (
        f"demo exited {result.returncode}\n{(result.stderr or '')[-2000:]}")
    assert result.stdout.strip()
