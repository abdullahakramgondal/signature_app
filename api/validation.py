import cv2
import numpy as np
from fastapi import HTTPException, UploadFile

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_BYTES = 5 * 1024 * 1024  # 5 MB


async def read_image(file: UploadFile) -> np.ndarray:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, "Only JPG, PNG or WEBP images are allowed.")
    data = await file.read()
    if len(data) == 0:
        raise HTTPException(400, "The uploaded file is empty.")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "The file is larger than 5 MB.")
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(400, "The image could not be decoded (corrupted file).")
    return img