"""Signature similarity: ONNX embedding model (ResNet18, 96x96) + cosine similarity."""
import json
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image

WEIGHTS_DIR = Path(__file__).parent / "weights"
MODEL_PATH = WEIGHTS_DIR / "similarity.onnx"
INFO_PATH = WEIGHTS_DIR / "similarity_model_info.json"

S = 96
THRESHOLD = 0.487  # overridden by the info json when it exists

_session = None


def get_session() -> ort.InferenceSession:
    global _session, THRESHOLD
    if _session is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"Model not found: {MODEL_PATH}")
        _session = ort.InferenceSession(str(MODEL_PATH), providers=["CPUExecutionProvider"])
        if INFO_PATH.exists():
            with open(INFO_PATH) as f:
                THRESHOLD = json.load(f)["threshold_similar_if_score_above"]
    return _session


def get_threshold() -> float:
    get_session()  # makes sure the threshold from the info json is loaded
    return THRESHOLD


def norm_sig(im: Image.Image) -> np.ndarray:
    """Exactly the same preprocessing as in training."""
    g = np.asarray(im.convert("L"), dtype=np.float32)
    bg = np.percentile(g[::4, ::4], 95)
    ink = np.clip(bg - g, 0, None)
    m = ink.max()
    if m > 0:
        ink = ink / m
    ys, xs = np.where(ink > 0.2)
    crop = ink if len(ys) == 0 else ink[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = crop.shape
    s = max(h, w)
    canvas = np.zeros((s, s), np.float32)
    canvas[(s - h) // 2:(s - h) // 2 + h, (s - w) // 2:(s - w) // 2 + w] = crop
    return np.asarray(
        Image.fromarray((canvas * 255).astype(np.uint8)).resize((S, S), Image.Resampling.LANCZOS)
    )


def embed(img_bgr: np.ndarray) -> np.ndarray:
    pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    x = norm_sig(pil).astype(np.float32) / 255.0
    x = ((x - 0.5) / 0.5)[None, None]  # (1, 1, 96, 96)
    session = get_session()
    return session.run(None, {"image": x})[0][0]  # already L2-normalized


def compute_similarity(img_a: np.ndarray, img_b: np.ndarray) -> float:
    """Cosine similarity in [-1, 1]. A score above THRESHOLD means the same signer."""
    return float(np.dot(embed(img_a), embed(img_b)))