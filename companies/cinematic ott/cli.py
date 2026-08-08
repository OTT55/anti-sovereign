"""cli.py — the command-line entry point.

    python cli.py --ref evalset/samples/ref1.jpg --target evalset/samples/t1.jpg

Wired up fully in Phase 6 (runs the whole segment -> analyze -> plan -> execute
-> critic loop and writes runs/<timestamp>/). For now it is a stub so the
skeleton imports cleanly.
"""

import argparse


def main():
    parser = argparse.ArgumentParser(
        description="Cinematic OTT — apply the CAUSES of a reference look to your photo."
    )
    parser.add_argument("--ref", required=True, help="Reference image (the look you want).")
    parser.add_argument("--target", required=True, help="Your photo to grade.")
    args = parser.parse_args()

    print(
        "The grading pipeline is not wired up yet — that happens in Phase 6.\n"
        f"  reference: {args.ref}\n"
        f"  target:    {args.target}\n"
        "Phase 0 (environment) and the modules are being built first, one phase at a time."
    )


if __name__ == "__main__":
    main()
