"""
Launch every Sovereign Stack & Anti-Sovereign app MVP at once.

Starts each Flask app on its assigned port as a subprocess and prints the URLs.
Includes Central Gateway (5000) and AI Labs Connector (5200).

    python companies/run_all.py
"""

import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).parent

# (folder, port, label)
APPS = [
    ("gateway",        5000, "Sovereign Gateway — Infrastructure Launchpad"),
    ("canonchain",     5101, "Canonchain — Rights Registry"),
    ("veridact",       5102, "Veridact — Truth Infrastructure"),
    ("nullform",       5103, "Nullform — Identity Layer"),
    ("clearpath",      5104, "Clearpath — Compliance Routing"),
    ("sovereign-edit", 5105, "Sovereign Edit — Certification"),
    ("strata-finance", 5106, "Strata Finance — Capital Settlement"),
    ("contextcore",    5107, "ContextCore — Data Refineries (RAG + collections)"),
    ("arcvault",       5108, "ArcVault — IP Arbitrage"),
    ("story-atlas",    5109, "Story Atlas — Creative Intelligence Workspace"),
    ("ai-labs",        5200, "AI Labs Connector — Noyron, Claude & Local LLM Mesh"),
]

# Collections that need seeding before their app starts (idempotent)
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
    print("\n🚀 Anti-Sovereign Infrastructure — Initializing Services...\n")
    
    for folder, script in SEEDS:
        if (BASE / folder / script).exists():
            subprocess.run(
                [sys.executable, script], cwd=BASE / folder,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )

    procs = []
    for folder, port, label in APPS:
        cwd = BASE / folder
        if not cwd.exists():
            continue
        p = subprocess.Popen(
            [sys.executable, "-c", LAUNCH.format(port=port)],
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        procs.append(p)

    time.sleep(2)
    print("  ================================================================")
    print("  🌐 Sovereign Stack & AI Labs — All Services Live:")
    print("  ================================================================\n")
    for _folder, port, label in APPS:
        if (_folder == "gateway"):
            print(f"    ⭐ http://127.0.0.1:{port}   --> {label} (MAIN)")
        else:
            print(f"       http://127.0.0.1:{port}   {label}")
    print("\n  Press Ctrl+C to stop all.\n")

    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        for p in procs:
            p.terminate()
        print("\n  Stopped all services cleanly.")


if __name__ == "__main__":
    main()
