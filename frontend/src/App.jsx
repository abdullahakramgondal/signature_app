import { useEffect, useRef, useState } from "react";
import "./App.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const POLL_MS = 1000;
const MAX_POLLS = 60;

export default function App() {
  const [token, setToken] = useState(localStorage.getItem("token") || "");
  const [authMode, setAuthMode] = useState("login"); // login | register
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [authMsg, setAuthMsg] = useState("");

  const [docFile, setDocFile] = useState(null);
  const [refFile, setRefFile] = useState(null);
  const [docUrl, setDocUrl] = useState(null);
  const [refUrl, setRefUrl] = useState(null);
  const [status, setStatus] = useState("idle"); // idle | queued | started | finished | failed
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const canvasRef = useRef(null);

  function pickDoc(file) {
    if (docUrl) URL.revokeObjectURL(docUrl);
    setDocFile(file);
    setDocUrl(file ? URL.createObjectURL(file) : null);
    setResult(null);
    setError("");
    setStatus("idle");
  }

  function pickRef(file) {
    if (refUrl) URL.revokeObjectURL(refUrl);
    setRefFile(file);
    setRefUrl(file ? URL.createObjectURL(file) : null);
  }

  // draw the document with detected boxes
  useEffect(() => {
    if (!token || !docUrl || !canvasRef.current) return;
    const img = new Image();
    img.onload = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0);
      if (result && result.boxes) {
        ctx.lineWidth = Math.max(3, Math.round(img.width / 200));
        ctx.strokeStyle = "#16a34a";
        ctx.fillStyle = "#16a34a";
        ctx.font = `${Math.max(14, Math.round(img.width / 50))}px sans-serif`;
        result.boxes.forEach((b) => {
          ctx.strokeRect(b.x1, b.y1, b.x2 - b.x1, b.y2 - b.y1);
          ctx.fillText(
            `${(b.confidence * 100).toFixed(0)}%`,
            b.x1,
            Math.max(16, b.y1 - 6)
          );
        });
      }
    };
    img.src = docUrl;
  }, [token, docUrl, result]);

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  function logout() {
    localStorage.removeItem("token");
    setToken("");
    setResult(null);
    setStatus("idle");
  }

  async function handleAuth() {
    setAuthMsg("");
    try {
      if (authMode === "register") {
        const r = await fetch(`${API}/auth/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password }),
        });
        if (!r.ok) throw new Error((await r.json()).detail || "Register failed");
        setAuthMode("login");
        setAuthMsg("Account created. Please log in.");
        return;
      }
      const form = new URLSearchParams({ username, password });
      const r = await fetch(`${API}/auth/login`, { method: "POST", body: form });
      if (!r.ok) throw new Error((await r.json()).detail || "Login failed");
      const data = await r.json();
      localStorage.setItem("token", data.access_token);
      setToken(data.access_token);
      setPassword("");
    } catch (e) {
      setAuthMsg(e.message);
    }
  }

  async function handleVerify() {
    if (!docFile || !refFile) return;
    setError("");
    setResult(null);
    setStatus("queued");
    const authHeaders = { Authorization: `Bearer ${token}` };
    try {
      const form = new FormData();
      form.append("document", docFile);
      form.append("reference", refFile);
      const res = await fetch(`${API}/verify/async`, {
        method: "POST",
        body: form,
        headers: authHeaders,
      });
      if (res.status === 401) {
        logout();
        throw new Error("Session expired. Please log in again.");
      }
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Upload failed (${res.status})`);
      }
      const { job_id } = await res.json();

      for (let i = 0; i < MAX_POLLS; i++) {
        await sleep(POLL_MS);
        const r = await fetch(`${API}/jobs/${job_id}`, { headers: authHeaders });
        if (r.status === 401) {
          logout();
          throw new Error("Session expired. Please log in again.");
        }
        if (!r.ok) throw new Error(`Job lookup failed (${r.status})`);
        const job = await r.json();
        setStatus(job.status);
        if (job.status === "finished") {
          setResult(job.result);
          return;
        }
        if (job.status === "failed") {
          throw new Error(job.error || "Job failed");
        }
      }
      throw new Error("Timed out waiting for the result");
    } catch (e) {
      setError(e.message);
      setStatus("failed");
    }
  }

  const busy = status === "queued" || status === "started";

  // ---------- login screen ----------
  if (!token) {
    return (
      <div className="page">
        <h1>Signature Verification</h1>
        <div className="card" style={{ maxWidth: 360, cursor: "default" }}>
          <span>{authMode === "login" ? "Log in" : "Create account"}</span>
          <input
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <button className="verify" onClick={handleAuth}>
            {authMode === "login" ? "Log in" : "Register"}
          </button>
          <small
            style={{ cursor: "pointer" }}
            onClick={() =>
              setAuthMode(authMode === "login" ? "register" : "login")
            }
          >
            {authMode === "login"
              ? "No account? Register"
              : "Have an account? Log in"}
          </small>
          {authMsg && <div className="error">{authMsg}</div>}
        </div>
      </div>
    );
  }

  // ---------- main screen ----------
  return (
    <div className="page">
      <h1>Signature Verification</h1>
      <button onClick={logout}>Log out</button>
      <p className="sub">
        Upload a document and a reference signature. The system finds the
        signature in the document and compares it with the reference.
      </p>

      <div className="uploads">
        <label className="card">
          <span>Document</span>
          <input
            type="file"
            accept="image/*"
            onChange={(e) => pickDoc(e.target.files[0] || null)}
          />
          {docFile && <small>{docFile.name}</small>}
        </label>
        <label className="card">
          <span>Reference signature</span>
          <input
            type="file"
            accept="image/*"
            onChange={(e) => pickRef(e.target.files[0] || null)}
          />
          {refFile && <small>{refFile.name}</small>}
        </label>
      </div>

      <button
        className="verify"
        onClick={handleVerify}
        disabled={!docFile || !refFile || busy}
      >
        {busy ? `Working (${status})...` : "Verify"}
      </button>

      {error && <div className="error">{error}</div>}

      {result && (
        <div className="result">
          {result.score == null ? (
            <div className="badge warn">{result.message}</div>
          ) : (
            <>
              <div className={`badge ${result.is_similar ? "ok" : "bad"}`}>
                {result.is_similar ? "Match" : "No match"}
              </div>
              <p>{result.message}</p>
              <p className="meta">
                Score: <b>{result.score.toFixed(3)}</b> (threshold{" "}
                {result.threshold})
              </p>
            </>
          )}
          <p className="meta">Signatures found in document: {result.count}</p>
        </div>
      )}

      <div className="previews">
        {docUrl && (
          <div>
            <h3>Document</h3>
            <canvas ref={canvasRef} className="doc-canvas" />
          </div>
        )}
        {refUrl && (
          <div>
            <h3>Reference</h3>
            <img src={refUrl} alt="reference" className="ref-img" />
          </div>
        )}
      </div>
    </div>
  );
}