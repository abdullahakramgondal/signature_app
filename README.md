# Signature Verification System

Upload a **document** and a **reference signature**. The system detects the signature in the document (object detection), then compares it with the reference (similarity score) and returns **Match / No match**.

Built with FastAPI, Redis + RQ (queue and worker), ONNX Runtime, React (Vite), Docker Compose and JWT auth.

---

## 1. Architecture

```
                    ┌────────────────────┐
                    │  React frontend    │  (nginx, port 3000)
                    │  login, upload,    │
                    │  poll job status   │
                    └─────────┬──────────┘
                              │ HTTP + Bearer JWT
                              ▼
                    ┌────────────────────┐
                    │  FastAPI  (api/)   │  (port 8000)
                    │  /auth/*           │
                    │  /predict          │  sync endpoints
                    │  /similarity       │
                    │  /verify           │
                    │  /verify/async ────┼──┐ enqueue job
                    │  /jobs/{id}   ◄────┼──┼─ read job status/result
                    └─────────┬──────────┘  │
                              │             ▼
                     SQLite users.db   ┌──────────┐
                     (auth)            │  Redis   │  broker + result store
                                       │  queue   │  queue name: "verify"
                                       └────┬─────┘
                                            │ job pulled
                                            ▼
                                  ┌───────────────────┐
                                  │  RQ Worker        │
                                  │  worker/worker.py │
                                  │  run_verify()     │
                                  └─────────┬─────────┘
                                            ▼
                              ┌─────────────────────────┐
                              │ models/ (ONNX Runtime)  │
                              │ detector.py  YOLOX-S    │
                              │ similarity.py ResNet18  │
                              └─────────────────────────┘

Shared volume `jobdata` (/data): API writes uploaded images, worker reads and deletes them.
```

### Async verify flow

1. Frontend logs in, gets a JWT, stores it in `localStorage`.
2. `POST /verify/async` validates the images, saves them to `DATA_DIR/jobs/<job_id>/`, enqueues the job in Redis and returns `202 {job_id}`.
3. The worker picks the job up, runs `run_verify()` (detect, crop, embed, cosine similarity) and stores the result in Redis (TTL 1 hour).
4. Frontend polls `GET /jobs/{job_id}` every second until the status is `finished` or `failed`.
5. Failed jobs are retried up to 3 times (5s, 15s, 30s). Job files are deleted only after success.
6. Each job stores its `owner`, so users can only read their own jobs.

### Verify pipeline (`api/pipeline.py`)

1. Detect signatures in the document (YOLOX-S, conf 0.3). If none, return "No signature found".
2. Detect in the reference (lower conf 0.15). If none, return "No signature in reference".
3. Crop the top box from each (6 px margin).
4. Embed both crops with ResNet18 (96x96, L2-normalized) and compute the cosine similarity.
5. `is_similar = score > threshold` (default 0.487, or the value in `similarity_model_info.json`).

---

## 2. Folder structure

```
signature_app/
├── api/                    FastAPI backend
│   ├── main.py             app, routes, CORS, startup model loading
│   ├── auth.py             JWT + bcrypt + SQLite user store
│   ├── pipeline.py         run_verify(), shared by API and worker
│   ├── queue_client.py     Redis/RQ producer: enqueue_verify(), get_job()
│   ├── schemas.py          Pydantic request/response models
│   └── validation.py       image type / size / decode checks
├── worker/
│   └── worker.py           RQ worker, process_verify(folder)
├── models/
│   ├── detector.py         YOLOX ONNX inference + NMS
│   ├── similarity.py       ResNet18 ONNX embedding + cosine similarity
│   └── weights/            signature.onnx, similarity.onnx
├── frontend/               React + Vite app (App.jsx is the main UI)
│   ├── Dockerfile          build with node, serve with nginx
│   └── nginx.conf
├── docker/                 Dockerfile (API and worker image), Dockerfile.api, Dockerfile.worker
├── dockercompose.yml       redis + api + worker + frontend
├── requirements.txt        Python dependencies
└── README.md
```

---

## 3. Prerequisites

| Tool           | Version                    | Check              |
| -------------- | -------------------------- | ------------------ |
| Git            | any                        | `git --version`    |
| Python         | 3.11                       | `python --version` |
| Node.js        | 20+ (Docker image uses 22) | `node -v`          |
| Docker Desktop | recent                     | `docker --version` |

> **Windows users:** RQ workers use `fork()` and **do not run on native Windows**. Either use Docker (recommended) or WSL2 for the worker and Redis.

---

## 4. Run with Docker (easiest, recommended)

From the project root:

```bash
docker compose -f dockercompose.yml up --build
```

(If your team renames the file to `docker-compose.yml`, just run `docker compose up --build`.)

**Before you run it:**

- Install **Docker Desktop** and open it. Wait 2 to 3 minutes until it has fully started, then run the command above from the project root.
- Keep Docker Desktop open the whole time you use the app, otherwise the frontend and API will stop.
- The first build downloads and builds all images, so it can take a while. Later runs are much faster.
- You can clone the repo or download it as a ZIP and open it in VS Code. Run the command in the VS Code terminal exactly as written.
- If you only want to try the app, you do not need Docker at all. Use the deployed version in section 5.

| Service            | URL                          |
| ------------------ | ---------------------------- |
| Frontend           | http://localhost:3000        |
| API + Swagger docs | http://localhost:8000/docs   |
| Health check       | http://localhost:8000/health |

Useful commands:

```bash
docker compose -f dockercompose.yml up -d            # run in background
docker compose -f dockercompose.yml logs -f worker   # follow worker logs
docker compose -f dockercompose.yml ps               # list containers
docker compose -f dockercompose.yml down             # stop
docker compose -f dockercompose.yml down -v          # stop and delete volumes
docker compose -f dockercompose.yml build --no-cache # rebuild from scratch
```

---

## 5. Deployed version (AWS)

The app is deployed on AWS, so you can use it directly in the browser without Docker Desktop. The latest code is on GitHub (updated after deployment).

| What     | URL                         |
| -------- | --------------------------- |
| App      | http://3.25.92.169          |
| API docs | http://3.25.92.169/api/docs |

**Please note:**

- Use **http**, not https. The browser may show "Not secure". This is expected.
- Do not share these links outside the group. The server is public and anyone with the link can register and upload images.
- Do not upload real signatures or ID documents. Use test or sample images only.
- The server will be stopped after Tuesday's presentation, so the links will stop working after that.

**How it is deployed:**

- One EC2 instance (m7i-flex.large, Ubuntu) in a public subnet of a VPC in `ap-southeast-2` (Sydney).
- The same Docker Compose stack runs on the instance: frontend (nginx), API, Redis and worker. nginx on port 80 proxies `/api/*` to the FastAPI container.
- The security group allows only port 22 (SSH) and port 80 (HTTP).
- The ONNX models are not stored in the Git repo. They live in a private S3 bucket and are downloaded at startup through an IAM role with S3 read-only access.
- Updating the app: `git pull` on the instance, then redeploy the containers.
- Traces and logs are sent to Logfire.

---

## 6. Run locally without Docker (for development)

Use 4 terminals, all from the project root. On Windows, run steps 1-3 in WSL2.

**Terminal 1: Redis**

```bash
docker run --rm -p 6379:6379 redis:7
```

**Terminal 2: API**

```bash
python -m venv venv
source venv/bin/activate            # Windows (PowerShell): venv\Scripts\Activate.ps1
pip install -r requirements.txt
export PYTHONPATH=.                 # PowerShell: $env:PYTHONPATH="."
uvicorn api.main:app --reload --port 8000
```

**Terminal 3: Worker**

```bash
source venv/bin/activate
export PYTHONPATH=.
python -m worker.worker
```

**Terminal 4: Frontend**

```bash
cd frontend
npm install
npm run dev                         # http://localhost:5173
```

### Environment variables

| Variable       | Default                    | Used by                           |
| -------------- | -------------------------- | --------------------------------- |
| `REDIS_URL`    | `redis://localhost:6379/0` | api, worker                       |
| `DATA_DIR`     | `./data`                   | api, worker (job files, users.db) |
| `JWT_SECRET`   | `change-me-in-production`  | api                               |
| `JWT_MINUTES`  | `60`                       | api                               |
| `VITE_API_URL` | `http://localhost:8000`    | frontend (build time)             |

---

## 7. Testing the API

1. Open http://localhost:8000/docs
2. `POST /auth/register` with a username (3+ chars) and a password (6+ chars).
3. Click **Authorize** and log in.
4. Try `/predict`, `/similarity`, `/verify`, then `/verify/async` followed by `/jobs/{job_id}`.

With curl:

```bash
curl -X POST localhost:8000/auth/register -H "Content-Type: application/json" \
     -d '{"username":"alice","password":"secret123"}'

TOKEN=$(curl -s -X POST localhost:8000/auth/login -d "username=alice&password=secret123" \
        | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -X POST localhost:8000/verify/async -H "Authorization: Bearer $TOKEN" \
     -F document=@doc.png -F reference=@sig.png

curl localhost:8000/jobs/<job_id> -H "Authorization: Bearer $TOKEN"
```

---

## 8. API reference

| Method | Path             | Auth | Description                                          |
| ------ | ---------------- | ---- | ---------------------------------------------------- |
| GET    | `/health`        | no   | liveness check                                       |
| POST   | `/auth/register` | no   | create user                                          |
| POST   | `/auth/login`    | no   | returns JWT (form fields)                            |
| POST   | `/predict`       | yes  | detect signatures in one image                       |
| POST   | `/similarity`    | yes  | similarity score of two images                       |
| POST   | `/verify`        | yes  | detect + compare, synchronous                        |
| POST   | `/verify/async`  | yes  | enqueue verify job, returns `job_id` (202)           |
| GET    | `/jobs/{job_id}` | yes  | status: queued, started, finished, failed, not_found |

---

## 9. Troubleshooting

| Problem                                | Fix                                                                 |
| -------------------------------------- | ------------------------------------------------------------------- |
| `Model not found: ...signature.onnx`   | Make sure `models/weights/*.onnx` exist (pull LFS or ask the team). |
| `ModuleNotFoundError: api` or `models` | Run from the project root and set `PYTHONPATH=.`                    |
| Worker crashes on Windows (`fork`)     | Use Docker or WSL2.                                                 |
| `Connection refused` to Redis          | Redis not running, or wrong `REDIS_URL`.                            |
| Job stays `queued`                     | Worker is not running, or it uses a different Redis or queue name.  |
| Login works but a request returns 401  | The token expired (60 min) or `JWT_SECRET` changed.                 |
| Frontend cannot reach the API          | Check `VITE_API_URL` and CORS.                                      |

---
