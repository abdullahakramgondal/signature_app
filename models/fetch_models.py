"""Download model weights from S3 if they are missing."""
import os
from pathlib import Path

WEIGHTS_DIR = Path(__file__).parent / "weights"
BUCKET = os.getenv("MODEL_BUCKET")
REGION = os.getenv("AWS_REGION", "ap-southeast-2")
FILES = ["signature.onnx", "similarity.onnx"]


def ensure_models() -> None:
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    missing = [f for f in FILES if not (WEIGHTS_DIR / f).exists()]
    if not missing:
        return
    if not BUCKET:
        raise RuntimeError("MODEL_BUCKET is not set and model files are missing.")
    import boto3
    s3 = boto3.client("s3", region_name=REGION)
    for name in missing:
        print(f"Downloading {name} from s3://{BUCKET}/{name}", flush=True)
        s3.download_file(BUCKET, name, str(WEIGHTS_DIR / name))