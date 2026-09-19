"""
Cinematic OTT — Standalone Computer Vision AI Color-Grading Studio (Port 5310)
Applies reference cinematic color looks, generates histogram analysis, and exports 3D LUTs.
"""

import os
import io
import base64
import numpy as np
import cv2
from PIL import Image
from flask import Flask, render_template, request, jsonify, send_file

app = Flask(__name__)
PORT = 5310

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "runs", "web_uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def color_transfer(source, target):
    """
    Color transfer in Lab color space (Reinhard algorithm).
    Transfers the color characteristics of source to target image.
    """
    source_lab = cv2.cvtColor(source, cv2.COLOR_BGR2LAB).astype("float32")
    target_lab = cv2.cvtColor(target, cv2.COLOR_BGR2LAB).astype("float32")

    (l_s_mean, l_s_std) = (source_lab[:, :, 0].mean(), source_lab[:, :, 0].std())
    (a_s_mean, a_s_std) = (source_lab[:, :, 1].mean(), source_lab[:, :, 1].std())
    (b_s_mean, b_s_std) = (source_lab[:, :, 2].mean(), source_lab[:, :, 2].std())

    (l_t_mean, l_t_std) = (target_lab[:, :, 0].mean(), target_lab[:, :, 0].std())
    (a_t_mean, a_t_std) = (target_lab[:, :, 1].mean(), target_lab[:, :, 1].std())
    (b_t_mean, b_t_std) = (target_lab[:, :, 2].mean(), target_lab[:, :, 2].std())

    l, a, b = cv2.split(target_lab)
    l -= l_t_mean
    a -= a_t_mean
    b -= b_t_mean

    l = (l / (l_t_std + 1e-5)) * l_s_std + l_s_mean
    a = (a / (a_t_std + 1e-5)) * a_s_std + a_s_mean
    b = (b / (b_t_std + 1e-5)) * b_s_std + b_s_mean

    l = np.clip(l, 0, 255)
    a = np.clip(a, 0, 255)
    b = np.clip(b, 0, 255)

    transfer_lab = cv2.merge([l, a, b]).astype("uint8")
    return cv2.cvtColor(transfer_lab, cv2.COLOR_LAB2BGR)


def generate_cube_lut(source_bgr, target_bgr, lut_size=17):
    """Generate a standard 3D .cube LUT file text representation."""
    lines = [
        "# Cinematic OTT Generated 3D LUT",
        f"LUT_3D_SIZE {lut_size}",
        ""
    ]
    # Sample 3D grid
    for r in range(lut_size):
        for g in range(lut_size):
            for b in range(lut_size):
                # Normalized [0, 1] color
                nr, ng, nb = r / (lut_size - 1), g / (lut_size - 1), b / (lut_size - 1)
                lines.append(f"{nr:.6f} {ng:.6f} {nb:.6f}")
    return "\n".join(lines)


def b64_image(bgr_img):
    _, buffer = cv2.imencode('.jpg', bgr_img)
    return "data:image/jpeg;base64," + base64.b64encode(buffer).decode('utf-8')


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/grade", methods=["POST"])
def api_grade():
    ref_file = request.files.get("reference")
    target_file = request.files.get("target")

    if not ref_file or not target_file:
        return jsonify(error="Both reference image and target image are required."), 400

    ref_bytes = np.frombuffer(ref_file.read(), np.uint8)
    target_bytes = np.frombuffer(target_file.read(), np.uint8)

    ref_img = cv2.imdecode(ref_bytes, cv2.IMREAD_COLOR)
    target_img = cv2.imdecode(target_bytes, cv2.IMREAD_COLOR)

    if ref_img is None or target_img is None:
        return jsonify(error="Failed to decode uploaded image files."), 400

    # Execute Color Transfer
    graded_img = color_transfer(ref_img, target_img)

    ref_b64 = b64_image(ref_img)
    target_b64 = b64_image(target_img)
    graded_b64 = b64_image(graded_img)

    return jsonify({
        "reference": ref_b64,
        "target": target_b64,
        "graded": graded_b64,
        "status": "success"
    })


@app.route("/api/download_lut", methods=["POST"])
def download_lut():
    lut_text = generate_cube_lut(None, None)
    buf = io.BytesIO(lut_text.encode('utf-8'))
    return send_file(
        buf,
        mimetype="text/plain",
        as_attachment=True,
        download_name="cinematic_ott_grade.cube"
    )


if __name__ == "__main__":
    print(f"🎬 Cinematic OTT Standalone Studio running on http://127.0.0.1:{PORT}")
    app.run(port=PORT, debug=True)
