from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import LOG_DIR


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_log(
    *,
    action: str,
    status: str,
    level: str = "INFO",
    user_id: str | None = None,
    experiment_uuid: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    why: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": _now(),
        "level": level,
        "service": "themis",
        "user_id": user_id,
        "action": action,
        "status": status,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "where": "backend",
        "why": why,
        "metadata": metadata or {},
    }
    if experiment_uuid:
        path = LOG_DIR / "experiments" / f"{experiment_uuid}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
    else:
        path = LOG_DIR / "system.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

