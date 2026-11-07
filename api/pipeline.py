"""Shared verify pipeline used by both the API and the worker."""
import numpy as np

from models.detector import detect
from models.similarity import compute_similarity, get_threshold

CROP_MARGIN = 6
REFERENCE_CONF = 0.15


def crop_box(img: np.ndarray, box: dict) -> np.ndarray:
    h, w = img.shape[:2]
    x1 = max(0, int(box["x1"]) - CROP_MARGIN)
    y1 = max(0, int(box["y1"]) - CROP_MARGIN)
    x2 = min(w, int(box["x2"]) + CROP_MARGIN)
    y2 = min(h, int(box["y2"]) + CROP_MARGIN)
    return img[y1:y2, x1:x2]


def run_verify(doc: np.ndarray, ref: np.ndarray) -> dict:
    h, w = doc.shape[:2]
    boxes = detect(doc)
    if not boxes:
        return {
            "image_width": w, "image_height": h, "count": 0, "boxes": [],
            "reference_found": True, "score": None, "threshold": None,
            "is_similar": None, "message": "No signature was found in the document.",
        }

    ref_boxes = detect(ref, conf_threshold=REFERENCE_CONF)
    if not ref_boxes:
        return {
            "image_width": w, "image_height": h, "count": len(boxes), "boxes": boxes,
            "reference_found": False, "score": None, "threshold": None,
            "is_similar": None, "message": "No signature was found in the reference image.",
        }

    score = compute_similarity(crop_box(doc, boxes[0]), crop_box(ref, ref_boxes[0]))
    threshold = get_threshold()
    is_similar = bool(score > threshold)
    return {
        "image_width": w, "image_height": h, "count": len(boxes), "boxes": boxes,
        "reference_found": True, "score": score, "threshold": threshold,
        "is_similar": is_similar,
        "message": "The signature matches the reference." if is_similar
        else "The signature does not match the reference.",
    }