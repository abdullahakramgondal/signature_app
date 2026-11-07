from typing import Optional

from pydantic import BaseModel


class Box(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float


class PredictResponse(BaseModel):
    image_width: int
    image_height: int
    count: int
    boxes: list[Box]


class SimilarityResponse(BaseModel):
    score: float


class VerifyResponse(BaseModel):
    image_width: int
    image_height: int
    count: int
    boxes: list[Box]
    reference_found: bool = True          # False if the reference image has no signature
    score: Optional[float] = None         # None if either image has no signature
    threshold: Optional[float] = None
    is_similar: Optional[bool] = None
    message: str


class JobCreated(BaseModel):
    job_id: str
    status: str = "queued"


class JobStatus(BaseModel):
    job_id: str
    status: str                       # queued, started, finished, failed, not_found
    result: Optional[VerifyResponse] = None
    error: Optional[str] = None

class Credentials(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"