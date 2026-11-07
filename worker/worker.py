"""RQ worker: runs the verify pipeline for queued jobs."""
import os
import shutil
from pathlib import Path

import cv2
import numpy as np
from redis import Redis
from rq import Queue, Worker

from api.pipeline import run_verify
from models.detector import get_session as get_detector_session
from models.similarity import get_session as get_similarity_session

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUE_NAME = "verify"


def _read(path: Path) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Could not decode image: {path.name}")
    return img


def process_verify(folder: str) -> dict:
    """Job function executed by the worker.

    Uploaded files are deleted only after success, so a retry can still read them.
    """
    folder_path = Path(folder)
    doc = _read(folder_path / "document.bin")
    ref = _read(folder_path / "reference.bin")
    result = run_verify(doc, ref)
    shutil.rmtree(folder_path, ignore_errors=True)
    return result


if __name__ == "__main__":
    get_detector_session()      # load models once at startup
    get_similarity_session()
    conn = Redis.from_url(REDIS_URL)
    Worker([Queue(QUEUE_NAME, connection=conn)], connection=conn).work()