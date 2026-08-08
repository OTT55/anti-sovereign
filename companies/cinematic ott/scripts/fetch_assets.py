"""scripts/fetch_assets.py — download the model files and sample images Phase 2 needs.

Run once after setup:

    python scripts/fetch_assets.py

Downloads (with resume, because this network drops large transfers):
  models/selfie_multiclass_256x256.tflite  — MediaPipe ImageSegmenter. Segments a person
      into background / hair / body-skin / face-skin / clothes / others. This is what gives
      us `hair`, `skin`, `face`, and `clothing` regions.
  models/face_landmarker.task              — MediaPipe FaceLandmarker. 478 facial landmarks,
      used for the precise `face` region and the `eyes` region (which must never be hue-shifted).
  evalset/samples/*.jpg                    — real photographs with people, for Phase 2 tests.

Everything here is downloaded, not committed (see .gitignore).
"""

import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.path.join(ROOT, "models")
SAMPLES = os.path.join(ROOT, "evalset", "samples")

MP = "https://storage.googleapis.com/mediapipe-models"
ASSETS = [
    (os.path.join(MODELS, "selfie_multiclass_256x256.tflite"),
     f"{MP}/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite"),
    (os.path.join(MODELS, "face_landmarker.task"),
     f"{MP}/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"),
    # Real photographs (ultralytics' public test assets): two people with visible faces,
    # and a street scene with people + a vehicle — good coverage for our semantic classes.
    (os.path.join(SAMPLES, "people.jpg"),
     "https://raw.githubusercontent.com/ultralytics/assets/main/im/zidane.jpg"),
    (os.path.join(SAMPLES, "street.jpg"),
     "https://raw.githubusercontent.com/ultralytics/assets/main/im/bus.jpg"),
]


def fetch(path: str, url: str, attempts: int = 40) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    name = os.path.basename(path)

    # Determine the expected size so we know when a resumed file is complete.
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60) as r:
            total = int(r.headers.get("Content-Length") or 0)
    except Exception:
        total = 0

    for attempt in range(1, attempts + 1):
        have = os.path.getsize(path) if os.path.exists(path) else 0
        if total and have >= total:
            print(f"  ok  {name} ({have / 1048576:.1f} MB)")
            return
        headers = {"Range": f"bytes={have}-"} if have else {}
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=120) as resp, open(path, "ab") as fh:
                while True:
                    chunk = resp.read(262144)
                    if not chunk:
                        break
                    fh.write(chunk)
            if not total:  # no Content-Length: one clean pass is all we can verify
                print(f"  ok  {name} ({os.path.getsize(path) / 1048576:.1f} MB)")
                return
        except Exception as e:
            got = os.path.getsize(path) if os.path.exists(path) else 0
            print(f"  .. {name}: {type(e).__name__} at {got / 1048576:.1f} MB — resuming")
            time.sleep(2)
    raise SystemExit(f"gave up downloading {name}")


if __name__ == "__main__":
    print("Fetching Phase 2 assets (models + real sample photos)…")
    for path, url in ASSETS:
        fetch(path, url)
    print("done")
