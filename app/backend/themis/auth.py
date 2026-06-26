from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fastapi import Depends, Header, HTTPException, status

from .config import ENV_DIR

Role = Literal["admin", "labeler"]


@dataclass(frozen=True)
class CurrentUser:
    username: str
    role: Role


_sessions: dict[str, CurrentUser] = {}


def md5_password(password: str) -> str:
    return hashlib.md5(password.encode("utf-8")).hexdigest()


def users_path() -> Path:
    path = ENV_DIR / "users.json"
    if not path.exists():
        example = ENV_DIR / "users.example.json"
        if example.exists():
            return example
    return path


def load_users() -> list[dict]:
    path = users_path()
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("users", [])


def save_users(users: list[dict]) -> None:
    ENV_DIR.mkdir(parents=True, exist_ok=True)
    with (ENV_DIR / "users.json").open("w", encoding="utf-8") as fh:
        json.dump({"users": users}, fh, ensure_ascii=False, indent=2)


def authenticate(username: str, password: str) -> CurrentUser | None:
    password_md5 = md5_password(password)
    for user in load_users():
        if user.get("username") == username and user.get("password_md5") == password_md5 and user.get("active", True):
            role = user.get("role")
            if role in ("admin", "labeler"):
                return CurrentUser(username=username, role=role)
    return None


def create_session(user: CurrentUser) -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = user
    return token


def destroy_session(token: str) -> None:
    _sessions.pop(token, None)


def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    user = _sessions.get(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    return user


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user


def require_labeler_or_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role not in ("admin", "labeler"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Labeler role required")
    return user

