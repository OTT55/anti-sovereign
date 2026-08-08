"""scripts/smoke.py — Phase 0 acceptance test.

Checks each subsystem INDEPENDENTLY and reports which pass, so that (for example)
a billing problem on the API can't hide the fact that the vision stack works.

    python scripts/smoke.py

Prints "ALL SYSTEMS OK" only if every check passes. Otherwise it prints a clear
per-system report and exits non-zero.
"""

import os
import sys
import tempfile

# Make the project importable and locate paths relative to the repo root.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Routed through OpenRouter (src/vlm_client.py), so the id is an OpenRouter model slug,
# not a raw provider model name. Configurable — see scripts/test_vision_models.py for how
# to compare candidates before picking one for a given phase.
MODEL = "anthropic/claude-sonnet-5"

try:
    from rich.console import Console
    _c = Console()
    def say(msg): _c.print(msg)
except Exception:  # rich not installed yet — degrade to plain print
    import re
    def say(msg): print(re.sub(r"\[/?[a-z ]+\]", "", msg))


# --- individual checks: each returns a short detail string or raises ----------
def check_cv():
    import numpy as np
    import cv2
    img = np.zeros((32, 48, 3), dtype=np.uint8)
    img[:, :, 2] = 200  # red channel (BGR)
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.png")
        assert cv2.imwrite(p, img), "cv2.imwrite failed"
        back = cv2.imread(p)
    assert back is not None and back.shape == (32, 48, 3), "image round-trip failed"
    return f"cv2 {cv2.__version__}, numpy {np.__version__} — image round-trip OK"


def check_yolo():
    import numpy as np
    from ultralytics import YOLO
    weights = os.path.join(ROOT, "yolov8s-seg.pt")
    model = YOLO(weights if os.path.exists(weights) else "yolov8s-seg.pt")
    dummy = np.zeros((320, 320, 3), dtype=np.uint8)
    r = model.predict(dummy, verbose=False)
    assert r is not None, "predict returned None"
    return "loaded yolov8s-seg and ran one inference"


def check_mediapipe():
    # mediapipe >=0.10.30 removed the legacy `mp.solutions` API; the Tasks API replaces it.
    # FaceLandmarker -> face/eyes/skin regions, ImageSegmenter -> hair/skin/background (Phase 2).
    import mediapipe as mp
    from mediapipe.tasks.python import vision
    assert hasattr(vision, "FaceLandmarker"), "FaceLandmarker missing from mediapipe Tasks API"
    assert hasattr(vision, "ImageSegmenter"), "ImageSegmenter missing from mediapipe Tasks API"
    return f"mediapipe {mp.__version__} (Tasks API: FaceLandmarker + ImageSegmenter)"


def check_api():
    # Routed through the one shared client (src/vlm_client.py) — no provider SDK is
    # imported here directly, matching the "one place we talk to a VLM" rule.
    from src.vlm_client import ask_the_model

    dummy = os.path.join(ROOT, "evalset", "samples", "people.jpg")
    if not os.path.exists(dummy):
        raise RuntimeError("no sample image found (run: python scripts/fetch_assets.py)")
    text = ask_the_model(dummy, "Reply with exactly: SYSTEMS OK", model=MODEL)
    return f"model {MODEL} replied: {text.strip()!r}"


CHECKS = [
    ("OpenCV + NumPy", check_cv),
    ("YOLOv8-seg (ultralytics)", check_yolo),
    ("MediaPipe", check_mediapipe),
    ("OpenRouter vision API", check_api),
]


def main():
    say("[bold]Cinematic OTT — Phase 0 smoke test[/bold]\n")
    results = {}
    for name, fn in CHECKS:
        say(f"[bold]- {name}[/bold] …")
        try:
            detail = fn()
            results[name] = (True, detail)
            say(f"  [green]PASS[/green] {detail}")
        except Exception as e:
            results[name] = (False, f"{type(e).__name__}: {e}")
            say(f"  [red]FAIL[/red] {results[name][1]}")

    say("\n[bold]Summary[/bold]")
    ok = True
    for name, (passed, detail) in results.items():
        tag = "[green]OK  [/green]" if passed else "[red]FAIL[/red]"
        say(f"  {tag} {name} — {detail}")
        ok = ok and passed

    say("")
    if ok:
        say("[green][bold]ALL SYSTEMS OK[/bold][/green]")
        sys.exit(0)
    say("[yellow]Some systems are not ready (see FAIL lines above).[/yellow]")
    sys.exit(1)


if __name__ == "__main__":
    main()
