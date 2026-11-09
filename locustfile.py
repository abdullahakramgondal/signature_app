import time

from locust import HttpUser, task, between

HOST_USER = "loadtest"
HOST_PASS = "loadtest123"


class SignatureUser(HttpUser):
    wait_time = between(1, 2)

    def on_start(self):
        # 409 = user already exists, expected for every user after the first
        with self.client.post(
            "/api/auth/register",
            json={"username": HOST_USER, "password": HOST_PASS},
            name="/auth/register",
            catch_response=True,
        ) as r:
            if r.status_code in (201, 409):
                r.success()

        r = self.client.post(
            "/api/auth/login",
            data={"username": HOST_USER, "password": HOST_PASS},
            name="/auth/login",
        )
        self.headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

        with open("test_doc.png", "rb") as f:
            self.doc = f.read()
        with open("test_ref.png", "rb") as f:
            self.ref = f.read()

    @task(3)
    def predict(self):
        self.client.post(
            "/api/predict",
            headers=self.headers,
            files={"file": ("doc.png", self.doc, "image/png")},
            name="/predict",
        )

    @task(1)
    def verify_sync(self):
        self.client.post(
            "/api/verify",
            headers=self.headers,
            files={
                "document": ("doc.png", self.doc, "image/png"),
                "reference": ("ref.png", self.ref, "image/png"),
            },
            name="/verify",
        )

    @task(1)
    def verify_async(self):
        # queue path: API returns a job_id (202), worker processes in background
        r = self.client.post(
            "/api/verify/async",
            headers=self.headers,
            files={
                "document": ("doc.png", self.doc, "image/png"),
                "reference": ("ref.png", self.ref, "image/png"),
            },
            name="/verify/async",
        )
        if r.status_code != 202:
            return
        job_id = r.json()["job_id"]
        for _ in range(60):
            time.sleep(1)
            j = self.client.get(
                f"/api/jobs/{job_id}",
                headers=self.headers,
                name="/jobs/[id]",
            )
            if j.status_code == 200 and j.json().get("status") in ("finished", "failed"):
                break