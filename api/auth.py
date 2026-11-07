"""JWT authentication with a small SQLite user store."""
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

SECRET_KEY = os.getenv("JWT_SECRET", "change-me-in-production")
ALGORITHM = "HS256"
TOKEN_MINUTES = int(os.getenv("JWT_MINUTES", "60"))
DB_PATH = Path(os.getenv("DATA_DIR", "./data")) / "users.db"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "username TEXT PRIMARY KEY, password_hash BLOB NOT NULL)"
    )
    return conn


def create_user(username: str, password: str) -> bool:
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    try:
        with _conn() as conn:
            conn.execute("INSERT INTO users VALUES (?, ?)", (username, hashed))
        return True
    except sqlite3.IntegrityError:
        return False


def verify_user(username: str, password: str) -> bool:
    with _conn() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
    return bool(row) and bcrypt.checkpw(password.encode(), row[0])


def create_token(username: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MINUTES)
    return jwt.encode({"sub": username, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    err = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Invalid or expired token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise err
    username = payload.get("sub")
    if not username:
        raise err
    return username