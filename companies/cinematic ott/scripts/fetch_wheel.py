"""scripts/fetch_wheel.py — resumably download a PyPI wheel for this interpreter.

This machine's connection drops large transfers mid-stream (ConnectionResetError /
IncompleteRead), which makes plain `pip install` fail on big wheels (torch, polars).
This helper downloads with HTTP Range resume and retries until the file is complete,
then you install from the local file:

    python scripts/fetch_wheel.py polars-runtime-32
    pip install --find-links wheels/ ultralytics

Usage: python scripts/fetch_wheel.py <package> [<package> ...]
"""

import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WHEELS = os.path.join(ROOT, "wheels")

PY_TAGS = ("cp313", "cp310", "cp39", "py3", "abi3")  # accepted, in rough preference order


def pick_wheel(pkg: str):
    """Return (filename, url, size) of the best wheel for Windows + this Python."""
    with urllib.request.urlopen(f"https://pypi.org/pypi/{pkg}/json", timeout=60) as r:
        data = json.load(r)
    version = data["info"]["version"]
    candidates = []
    for f in data["releases"][version]:
        name = f["filename"]
        if not name.endswith(".whl"):
            continue
        # Platform tag must be Windows x64 or the pure-python "any".
        # NB: test the real tag, not a substring — "any" appears inside "manylinux".
        if "win_amd64" not in name and not name.endswith("-any.whl"):
            continue
        if not any(t in name for t in PY_TAGS):
            continue
        # prefer cp313, then abi3/py3 wheels
        rank = next((i for i, t in enumerate(PY_TAGS) if t in name), len(PY_TAGS))
        candidates.append((rank, name, f["url"], f["size"]))
    if not candidates:
        raise SystemExit(f"no suitable Windows wheel found for {pkg} {version}")
    candidates.sort()
    _, name, url, size = candidates[0]
    return name, url, size


def fetch(pkg: str, attempts: int = 60) -> str:
    name, url, size = pick_wheel(pkg)
    os.makedirs(WHEELS, exist_ok=True)
    path = os.path.join(WHEELS, name)
    print(f"{pkg}: {name} ({size / 1048576:.1f} MB)")

    for attempt in range(1, attempts + 1):
        have = os.path.getsize(path) if os.path.exists(path) else 0
        if have >= size:
            print(f"  complete: {path}")
            return path
        req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp, open(path, "ab") as fh:
                while True:
                    chunk = resp.read(262144)  # 256 KB
                    if not chunk:
                        break
                    fh.write(chunk)
        except Exception as e:
            got = os.path.getsize(path) if os.path.exists(path) else 0
            print(f"  attempt {attempt}: {type(e).__name__} at {got / 1048576:.1f}/{size / 1048576:.1f} MB — resuming")
            time.sleep(2)
            continue
    have = os.path.getsize(path) if os.path.exists(path) else 0
    if have < size:
        raise SystemExit(f"{pkg}: gave up at {have}/{size} bytes")
    return path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    for pkg in sys.argv[1:]:
        fetch(pkg)
    print("done")
