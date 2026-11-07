from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm

from api.auth import create_token, create_user, get_current_user, verify_user
from api.pipeline import run_verify
from api.queue_client import enqueue_verify, get_job
from api.schemas import (
    Credentials, JobCreated, JobStatus, PredictResponse, SimilarityResponse,
    TokenResponse, VerifyResponse,
)
from api.validation import read_image
from models import similarity as sim_model
from models.detector import detect, get_session as get_detector_session
from models.similarity import compute_similarity

app = FastAPI(title="Signature API", version="0.6.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


@app.on_event("startup")
def load_models():
    get_detector_session()
    sim_model.get_session()


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- auth ----------
@app.post("/auth/register", status_code=201)
def register(body: Credentials):
    if len(body.username) < 3 or len(body.password) < 6:
        raise HTTPException(400, "Username needs 3+ chars and password 6+ chars.")
    if not create_user(body.username, body.password):
        raise HTTPException(409, "Username already exists.")
    return {"message": "User created."}


@app.post("/auth/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends()):
    """Form fields (username, password) so the Swagger 'Authorize' button works."""
    if not verify_user(form.username, form.password):
        raise HTTPException(401, "Wrong username or password.")
    return TokenResponse(access_token=create_token(form.username))


# ---------- protected endpoints ----------
@app.post("/predict", response_model=PredictResponse)
async def predict(file: UploadFile = File(...), user: str = Depends(get_current_user)):
    img = await read_image(file)
    boxes = detect(img)
    h, w = img.shape[:2]
    return PredictResponse(image_width=w, image_height=h, count=len(boxes), boxes=boxes)


@app.post("/similarity", response_model=SimilarityResponse)
async def similarity(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...),
    user: str = Depends(get_current_user),
):
    img1 = await read_image(file1)
    img2 = await read_image(file2)
    return SimilarityResponse(score=compute_similarity(img1, img2))


@app.post("/verify", response_model=VerifyResponse)
async def verify(
    document: UploadFile = File(...),
    reference: UploadFile = File(...),
    user: str = Depends(get_current_user),
):
    doc = await read_image(document)
    ref = await read_image(reference)
    return VerifyResponse(**run_verify(doc, ref))


@app.post("/verify/async", response_model=JobCreated, status_code=202)
async def verify_async(
    document: UploadFile = File(...),
    reference: UploadFile = File(...),
    user: str = Depends(get_current_user),
):
    await read_image(document)
    await read_image(reference)
    await document.seek(0)
    await reference.seek(0)
    job_id = enqueue_verify(await document.read(), await reference.read(), owner=user)
    return JobCreated(job_id=job_id)


@app.get("/jobs/{job_id}", response_model=JobStatus)
def job_status(job_id: str, user: str = Depends(get_current_user)):
    info = get_job(job_id, owner=user)
    if info["status"] == "not_found":
        raise HTTPException(404, "Job not found (it may have expired).")
    return JobStatus(**info)