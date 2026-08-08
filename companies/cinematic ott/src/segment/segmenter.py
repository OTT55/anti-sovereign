"""Phase 2 — semantic segmentation.

Turns an image into a set of named regions the rest of the pipeline can target:

    masks = segment_image("photo.jpg")
    masks["face"]   # uint8 array, 255 where face, 0 elsewhere

Why two models instead of one:
  * **YOLOv8-seg** knows about *objects in a scene* — people, vehicles, plants. It gives us
    the person's silhouette and named scene objects.
  * **MediaPipe** knows about *people specifically* — it separates a person into hair,
    body-skin, face-skin and clothes, and locates 478 facial landmarks. That's what lets us
    protect faces and eyes precisely, which YOLO alone cannot do.
  * **Sky** is not in either model's vocabulary, so it's a documented heuristic (see `_sky_mask`).

Every pixel ends up in exactly one class. Overlaps are resolved by PRIORITY (spec order):
    eyes > face > skin > hair > clothing > person > named objects > background_other
The narrowest, most protected region wins — so a pixel that is both "person" and "eye" is
an eye, and the eye protections apply to it.
"""

from __future__ import annotations

import os
from typing import Dict

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS = os.path.join(ROOT, "models")
SELFIE_MODEL = os.path.join(MODELS, "selfie_multiclass_256x256.tflite")
FACE_MODEL = os.path.join(MODELS, "face_landmarker.task")
YOLO_WEIGHTS = os.path.join(ROOT, "yolov8s-seg.pt")

# Resolution order: later entries win over earlier ones when they overlap.
PRIORITY = [
    "background_other",
    "sky", "foliage", "ground", "water", "building", "vehicle", "metal", "glass",
    "person",
    "clothing",
    "hair",
    "skin",
    "face",
    "eyes",
]

# COCO class name -> our semantic vocabulary. Anything unmapped stays background_other.
COCO_TO_SEMANTIC = {
    "person": "person",
    "car": "vehicle", "bus": "vehicle", "truck": "vehicle", "motorcycle": "vehicle",
    "bicycle": "vehicle", "train": "vehicle", "boat": "vehicle", "airplane": "vehicle",
    "potted plant": "foliage",
}

# MediaPipe selfie_multiclass channel order (fixed by the model).
MP_BACKGROUND, MP_HAIR, MP_BODY_SKIN, MP_FACE_SKIN, MP_CLOTHES, MP_OTHERS = range(6)

# Landmark indices for the two eye regions in MediaPipe's 478-point face mesh.
LEFT_EYE = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
RIGHT_EYE = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]


# --------------------------------------------------------------------------- #
#  utilities                                                                   #
# --------------------------------------------------------------------------- #
def feather(mask: np.ndarray, px: int) -> np.ndarray:
    """Soften a mask's edge by `px` pixels (Gaussian blur).

    Hard mask edges produce visible seams when a colour change is applied to one region and
    not its neighbour. Feathering makes the transition gradual.
    """
    if px <= 0:
        return mask.copy()
    k = int(px) * 2 + 1  # kernel must be odd
    return cv2.GaussianBlur(mask, (k, k), 0)


def _empty(shape) -> np.ndarray:
    return np.zeros(shape[:2], dtype=np.uint8)


# --------------------------------------------------------------------------- #
#  YOLO — scene objects                                                        #
# --------------------------------------------------------------------------- #
def _yolo_masks(image: np.ndarray) -> Dict[str, np.ndarray]:
    """Person / vehicle / foliage silhouettes from YOLOv8-seg."""
    from ultralytics import YOLO

    out: Dict[str, np.ndarray] = {}
    model = YOLO(YOLO_WEIGHTS if os.path.exists(YOLO_WEIGHTS) else "yolov8s-seg.pt")
    res = model.predict(image, verbose=False)[0]
    if res.masks is None:
        return out

    h, w = image.shape[:2]
    names = res.names
    for poly, cls_id in zip(res.masks.data, res.boxes.cls):
        label = names[int(cls_id)]
        semantic = COCO_TO_SEMANTIC.get(label)
        if semantic is None:
            continue
        m = poly.cpu().numpy().astype(np.uint8) * 255
        m = cv2.resize(m, (w, h), interpolation=cv2.INTER_NEAREST)
        out[semantic] = cv2.bitwise_or(out[semantic], m) if semantic in out else m
    return out


# --------------------------------------------------------------------------- #
#  MediaPipe — person parts + face landmarks                                   #
# --------------------------------------------------------------------------- #
def _mediapipe_person_parts(image: np.ndarray) -> Dict[str, np.ndarray]:
    """hair / skin / face / clothing from the selfie multiclass segmenter."""
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    if not os.path.exists(SELFIE_MODEL):
        return {}

    h, w = image.shape[:2]
    opts = vision.ImageSegmenterOptions(
        base_options=mp_python.BaseOptions(model_asset_path=SELFIE_MODEL),
        output_category_mask=True,
    )
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    with vision.ImageSegmenter.create_from_options(opts) as seg:
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = seg.segment(mp_img)

    cat = result.category_mask.numpy_view()
    cat = cv2.resize(cat, (w, h), interpolation=cv2.INTER_NEAREST)

    def band(idx):
        return ((cat == idx).astype(np.uint8)) * 255

    face_skin = band(MP_FACE_SKIN)
    body_skin = band(MP_BODY_SKIN)
    return {
        "hair": band(MP_HAIR),
        "clothing": band(MP_CLOTHES),
        "face": face_skin,
        # 'skin' is all visible skin (face + body); 'face' is the narrower, protected subset.
        "skin": cv2.bitwise_or(face_skin, body_skin),
    }


def _mediapipe_face_and_eyes(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (face_oval, eyes) from face-mesh landmarks.

    Eyes may never be hue-shifted (spec section 6). The face oval is unioned into the face
    mask so the protected face region covers the whole face, not just the pixels the
    segmentation model happened to label as 'face skin'.
    """
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision
    import mediapipe as mp

    h, w = image.shape[:2]
    eyes = _empty(image.shape)
    face_oval = _empty(image.shape)
    if not os.path.exists(FACE_MODEL):
        return face_oval, eyes

    # Deliberately permissive thresholds (default is 0.5, which missed a clearly visible
    # face in our own sample). The error is asymmetric: a MISSED face means the face/eye
    # protections never get applied to it — the exact failure the spec calls unacceptable.
    # An over-eager detection only means we protect a bit more area than strictly needed.
    # When in doubt, protect.
    opts = vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=FACE_MODEL),
        num_faces=5,
        min_face_detection_confidence=0.2,
        min_face_presence_confidence=0.2,
    )
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    with vision.FaceLandmarker.create_from_options(opts) as fl:
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = fl.detect(mp_img)

    for face in result.face_landmarks:
        for idx_set in (LEFT_EYE, RIGHT_EYE):
            pts = np.array(
                [[int(face[i].x * w), int(face[i].y * h)] for i in idx_set if i < len(face)],
                dtype=np.int32,
            )
            if len(pts) >= 3:
                cv2.fillPoly(eyes, [cv2.convexHull(pts)], 255)
        # Whole-face hull from every landmark — the protected face region.
        all_pts = np.array([[int(p.x * w), int(p.y * h)] for p in face], dtype=np.int32)
        if len(all_pts) >= 3:
            cv2.fillPoly(face_oval, [cv2.convexHull(all_pts)], 255)
    return face_oval, eyes


# --------------------------------------------------------------------------- #
#  Sky — documented heuristic (no model covers it)                             #
# --------------------------------------------------------------------------- #
def _sky_mask(image: np.ndarray, claimed: np.ndarray) -> np.ndarray:
    """Approximate sky: bright, blue-ish, in the upper third, not already claimed.

    Honest v0 heuristic (the build plan allows this). It is deliberately conservative — it
    would rather miss sky than steal pixels from a subject.
    """
    h, w = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]

    blueish = ((hue >= 90) & (hue <= 130) & (sat > 30)) | (sat < 30)  # blue, or near-white haze
    bright = val > 120
    sky = (blueish & bright).astype(np.uint8) * 255

    region = np.zeros((h, w), dtype=np.uint8)
    region[: int(h * 0.4), :] = 255          # only the top 40% of the frame
    sky = cv2.bitwise_and(sky, region)
    sky = cv2.bitwise_and(sky, cv2.bitwise_not(claimed))

    # Remove speckle.
    sky = cv2.morphologyEx(sky, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))

    # Real sky reaches the top of the frame. Requiring that kills the most common false
    # positive: bright, out-of-focus background (a blurred crowd reads as "blue-ish and
    # bright" but floats in the middle of the frame). Verified on evalset/samples/people.jpg,
    # where the naive version mislabelled 2.6% of a stadium crowd as sky.
    n, labels, stats, _ = cv2.connectedComponentsWithStats(sky, connectivity=8)
    keep = np.zeros_like(sky)
    min_area = 0.005 * h * w                     # ignore trivial specks
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < min_area:
            continue
        if stats[i, cv2.CC_STAT_TOP] > 2:        # must touch (near) the top edge
            continue
        keep[labels == i] = 255
    return keep


# --------------------------------------------------------------------------- #
#  main entry point                                                            #
# --------------------------------------------------------------------------- #
def segment_image(path_or_image, feather_px: int = 0) -> Dict[str, np.ndarray]:
    """Return {semantic_class: uint8 mask}. Every pixel belongs to exactly one class.

    Masks are mutually exclusive (priority-resolved). Pass `feather_px` > 0 to soften edges
    — note that feathered masks intentionally overlap at boundaries, which is what makes
    blending seamless; the exclusivity guarantee applies to the unfeathered result.
    """
    image = cv2.imread(path_or_image) if isinstance(path_or_image, str) else path_or_image
    if image is None:
        raise FileNotFoundError(f"could not read image: {path_or_image}")

    raw: Dict[str, np.ndarray] = {}
    raw.update(_yolo_masks(image))

    person = raw.get("person")
    parts = _mediapipe_person_parts(image)
    if person is not None:
        # Person-part models describe *a person*; constrain them to the detected silhouette
        # so a skin-coloured wall can't be labelled skin.
        parts = {k: cv2.bitwise_and(v, person) for k, v in parts.items()}
    raw.update(parts)

    face_oval, eyes = _mediapipe_face_and_eyes(image)
    if face_oval.any():
        # Union the landmark face oval with the model's 'face skin', so the protected face
        # region is the whole face. Constrained to the person silhouette where we have one.
        if person is not None:
            face_oval = cv2.bitwise_and(face_oval, person)
        raw["face"] = cv2.bitwise_or(raw.get("face", _empty(image.shape)), face_oval)
        # A face is also skin — keep 'skin' a superset so skin protections always cover it.
        raw["skin"] = cv2.bitwise_or(raw.get("skin", _empty(image.shape)), face_oval)
    if eyes.any():
        raw["eyes"] = eyes

    # Sky fills unclaimed upper-frame pixels.
    claimed_so_far = _empty(image.shape)
    for m in raw.values():
        claimed_so_far = cv2.bitwise_or(claimed_so_far, m)
    sky = _sky_mask(image, claimed_so_far)
    if sky.any():
        raw["sky"] = sky

    # --- resolve overlaps by priority: higher-priority classes claim pixels first ---
    final: Dict[str, np.ndarray] = {}
    claimed = _empty(image.shape)
    for name in reversed(PRIORITY):           # highest priority first
        if name not in raw:
            continue
        m = cv2.bitwise_and(raw[name], cv2.bitwise_not(claimed))
        final[name] = m
        claimed = cv2.bitwise_or(claimed, m)

    # Everything still unclaimed is background.
    final["background_other"] = cv2.bitwise_not(claimed)

    final = {k: v for k, v in final.items() if v.any()}
    if feather_px > 0:
        final = {k: feather(v, feather_px) for k, v in final.items()}
    return final


# --------------------------------------------------------------------------- #
#  debug overlay — so a human can SEE the masks                                #
# --------------------------------------------------------------------------- #
CLASS_COLORS = {
    "eyes": (255, 255, 0), "face": (0, 0, 255), "skin": (0, 128, 255),
    "hair": (128, 0, 128), "clothing": (0, 255, 0), "person": (255, 0, 255),
    "sky": (255, 200, 0), "vehicle": (0, 255, 255), "foliage": (0, 200, 0),
    "ground": (80, 80, 80), "water": (255, 128, 0), "building": (128, 128, 255),
    "background_other": (40, 40, 40),
}


def save_overlay(path_or_image, masks: Dict[str, np.ndarray], out_path: str) -> str:
    """Write a colour-coded PNG so the masks can be visually checked."""
    image = cv2.imread(path_or_image) if isinstance(path_or_image, str) else path_or_image
    layer = np.zeros_like(image)
    for name, mask in masks.items():
        color = CLASS_COLORS.get(name, (200, 200, 200))
        layer[mask > 127] = color
    blended = cv2.addWeighted(image, 0.55, layer, 0.45, 0)

    y = 24
    for name in sorted(masks):
        color = CLASS_COLORS.get(name, (200, 200, 200))
        pct = 100.0 * float((masks[name] > 127).sum()) / masks[name].size
        cv2.rectangle(blended, (10, y - 12), (26, y + 2), color, -1)
        cv2.putText(blended, f"{name} {pct:.1f}%", (32, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        y += 20

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    cv2.imwrite(out_path, blended)
    return out_path
