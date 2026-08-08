"""
Launch every Sovereign Stack company MVP at once.

Starts each Flask app on its own port as a subprocess and prints the URLs.
Press Ctrl+C to stop them all.

    python companies/run_all.py
"""

import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).parent

# (folder, port, label)
APPS = [
    ("canonchain",     5101, "Canonchain — Rights Registry"),
    ("veridact",       5102, "Veridact — Truth Infrastructure"),
    ("nullform",       5103, "Nullform — Identity Layer"),
    ("clearpath",      5104, "Clearpath — Compliance Routing"),
    ("sovereign-edit", 5105, "Sovereign Edit — Certification"),
    ("strata-finance", 5106, "Strata Finance — Capital Settlement"),
    ("contextcore",    5107, "ContextCore — Data Refineries (RAG + collections)"),
    ("arcvault",       5108, "ArcVault — IP Arbitrage"),
    ("story-atlas",    5109, "Story Atlas — Creative Intelligence Workspace"),
]

# Collections that need seeding before their app starts (idempotent — the
# seed script checks whether its collection is already populated).
SEEDS = [
    ("contextcore", "seed_distribution.py"),
]

# Boot each app with the reloader off so it runs as a single clean process.
LAUNCH = (
    "import app\n"
    "hasattr(app, 'init_db') and app.init_db()\n"
    "app.app.run(port={port}, use_reloader=False)\n"
)


def main():
    for folder, script in SEEDS:
        subprocess.run(
            [sys.executable, script], cwd=BASE / folder,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    procs = []
    for folder, port, label in APPS:
        cwd = BASE / folder
        p = subprocess.Popen(
            [sys.executable, "-c", LAUNCH.format(port=port)],
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        procs.append(p)

    time.sleep(2)
    print("\n  Sovereign Stack — company MVPs running:\n")
    for _folder, port, label in APPS:
        print(f"    http://127.0.0.1:{port}   {label}")
    print("\n  Press Ctrl+C to stop all.\n")

    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        for p in procs:
            p.terminate()
        print("\n  Stopped.")


if __name__ == "__main__":
    main()
