"""Signature detector: ONNX inference (YOLOX-S, 416x416).

Preprocessing matches training:
grayscale -> 3 channels, centered letterbox, padding value 114, no normalization.
"""
from models.fetch_models import ensure_models
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import onnxruntime as ort

WEIGHTS_DIR = Path(__file__).parent / "weights"
DETECTOR_PATH = WEIGHTS_DIR / "signature.onnx"

INPUT_SIZE = 416
CONF_THRESHOLD = 0.3
IOU_THRESHOLD = 0.45

_session = None


def get_session() -> ort.InferenceSession:
    global _session
    if _session is None:
        ensure_models()
        if not DETECTOR_PATH.exists():
            raise FileNotFoundError(f"Model not found: {DETECTOR_PATH}")
        _session = ort.InferenceSession(
            str(DETECTOR_PATH), providers=["CPUExecutionProvider"]
        )
    return _session


def preprocess(img_bgr: np.ndarray):
    """Grayscale, centered letterbox 416x416, pad 114, 3 channels, 0-255 range."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    r = min(INPUT_SIZE / h, INPUT_SIZE / w)
    nh, nw = int(round(h * r)), int(round(w * r))
    resized = cv2.resize(gray, (nw, nh), interpolation=cv2.INTER_LINEAR)

    canvas = np.full((INPUT_SIZE, INPUT_SIZE), 114, dtype=np.uint8)
    px, py = (INPUT_SIZE - nw) // 2, (INPUT_SIZE - nh) // 2
    canvas[py:py + nh, px:px + nw] = resized

    x = np.repeat(canvas[None], 3, axis=0)[None].astype(np.float32)  # (1, 3, 416, 416)
    return x, r, px, py


def postprocess(
    output: np.ndarray, r: float, px: int, py: int, img_w: int, img_h: int, conf: float
):
    """Model output [1, 3549, 6] = cx, cy, w, h, obj, cls -> boxes in original pixels."""
    o = output[0]
    scores = o[:, 4] * o[:, 5]
    mask = scores > conf
    o, scores = o[mask], scores[mask]
    if len(o) == 0:
        return []

    xywh = np.stack(
        [o[:, 0] - o[:, 2] / 2, o[:, 1] - o[:, 3] / 2, o[:, 2], o[:, 3]], axis=1
    )
    keep = cv2.dnn.NMSBoxes(xywh.tolist(), scores.tolist(), conf, IOU_THRESHOLD)
    keep = np.array(keep).flatten()

    results = []
    for i in keep:
        x, y, w, h = (float(v) for v in xywh[i])
        # remove letterbox padding, then scale back to the original image
        x, y = (x - px) / r, (y - py) / r
        w, h = w / r, h / r
        results.append(
            {
                "x1": max(0.0, x),
                "y1": max(0.0, y),
                "x2": min(float(img_w), x + w),
                "y2": min(float(img_h), y + h),
                "confidence": float(scores[i]),
            }
        )
    results.sort(key=lambda b: b["confidence"], reverse=True)
    return results


def detect(img_bgr: np.ndarray, conf_threshold: Optional[float] = None) -> list[dict]:
    conf = CONF_THRESHOLD if conf_threshold is None else conf_threshold
    h, w = img_bgr.shape[:2]
    x, r, px, py = preprocess(img_bgr)
    session = get_session()
    output = session.run(None, {session.get_inputs()[0].name: x})[0]
    return postprocess(output, r, px, py, w, h, conf)