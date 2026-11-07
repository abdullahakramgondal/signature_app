"""Redis queue client (producer side + job lookup)."""
import os
import uuid
from pathlib import Path

from redis import Redis
from rq import Queue, Retry
from rq.exceptions import NoSuchJobError
from rq.job import Job

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
QUEUE_NAME = "verify"
RESULT_TTL = 3600       # keep results for 1 hour
JOB_TIMEOUT = 120       # seconds

redis_conn = Redis.from_url(REDIS_URL)
queue = Queue(QUEUE_NAME, connection=redis_conn)


def enqueue_verify(doc_bytes: bytes, ref_bytes: bytes, owner: str) -> str:
    job_id = uuid.uuid4().hex
    folder = DATA_DIR / "jobs" / job_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "document.bin").write_bytes(doc_bytes)
    (folder / "reference.bin").write_bytes(ref_bytes)

    queue.enqueue(
        "worker.worker.process_verify",
        str(folder),
        job_id=job_id,
        result_ttl=RESULT_TTL,
        failure_ttl=RESULT_TTL,
        job_timeout=JOB_TIMEOUT,
        retry=Retry(max=3, interval=[5, 15, 30]),
        meta={"owner": owner},
    )
    return job_id


def get_job(job_id: str, owner: str) -> dict:
    """Return job info. Jobs owned by someone else are reported as not found."""
    try:
        job = Job.fetch(job_id, connection=redis_conn)
    except NoSuchJobError:
        return {"job_id": job_id, "status": "not_found"}

    if job.meta.get("owner") != owner:
        return {"job_id": job_id, "status": "not_found"}

    status = job.get_status()
    out = {"job_id": job_id, "status": status}
    if status == "finished":
        out["result"] = job.result
    elif status == "failed":
        out["error"] = (job.exc_info or "unknown error").strip().splitlines()[-1]
    return out