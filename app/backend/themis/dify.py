from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from .config import get_settings
from .models import ResponseMode, RunStatus


@dataclass
class DifyResult:
    status: RunStatus
    http_status: int | None
    request_payload: dict[str, Any]
    response_payload: dict[str, Any] | None
    error_message: str | None
    latency_ms: int | None
    started_at: datetime
    finished_at: datetime


def _request_payload(workflow_id: str, inputs: dict[str, Any], response_mode: ResponseMode) -> dict[str, Any]:
    return {
        "workflow_id": workflow_id,
        "inputs": inputs,
        "response_mode": response_mode.value,
        "user": "themis",
    }


def _extract_streaming_payload(text: str) -> tuple[dict[str, Any] | None, str | None]:
    last_payload: dict[str, Any] | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        raw = line.removeprefix("data:").strip()
        if not raw or raw == "[DONE]":
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if event.get("event") == "error":
            return event, event.get("message") or "Dify streaming error"
        if event.get("event") == "workflow_finished":
            data = event.get("data")
            if isinstance(data, dict) and data.get("error"):
                return event, str(data.get("error"))
            return event, None
        last_payload = event
    return last_payload, None


async def run_workflow(
    *,
    api_key: str,
    workflow_id: str,
    inputs: dict[str, Any],
    response_mode: ResponseMode,
) -> DifyResult:
    settings = get_settings()
    payload = _request_payload(workflow_id, inputs, response_mode)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = settings.dify_base_url.rstrip("/") + "/workflows/run"
    started = datetime.utcnow()
    monotonic = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=settings.dify_timeout_seconds) as client:
            response = await client.post(url, json=payload, headers=headers)
        latency_ms = int((time.perf_counter() - monotonic) * 1000)
        finished = datetime.utcnow()
        if response.status_code >= 400:
            return DifyResult(
                status=RunStatus.HTTP_ERROR,
                http_status=response.status_code,
                request_payload=payload,
                response_payload=_safe_json(response),
                error_message=response.text[:1000],
                latency_ms=None,
                started_at=started,
                finished_at=finished,
            )
        if response_mode == ResponseMode.STREAMING:
            body, stream_error = _extract_streaming_payload(response.text)
            return DifyResult(
                status=RunStatus.DIFY_ERROR if stream_error else RunStatus.SUCCESS,
                http_status=response.status_code,
                request_payload=payload,
                response_payload=body,
                error_message=stream_error,
                latency_ms=None if stream_error else latency_ms,
                started_at=started,
                finished_at=finished,
            )
        body = response.json()
        data = body.get("data") if isinstance(body, dict) else None
        if isinstance(data, dict) and data.get("error"):
            return DifyResult(
                status=RunStatus.DIFY_ERROR,
                http_status=response.status_code,
                request_payload=payload,
                response_payload=body,
                error_message=str(data.get("error")),
                latency_ms=None,
                started_at=started,
                finished_at=finished,
            )
        return DifyResult(
            status=RunStatus.SUCCESS,
            http_status=response.status_code,
            request_payload=payload,
            response_payload=body,
            error_message=None,
            latency_ms=latency_ms,
            started_at=started,
            finished_at=finished,
        )
    except httpx.TimeoutException as exc:
        finished = datetime.utcnow()
        return DifyResult(
            status=RunStatus.TIMEOUT,
            http_status=None,
            request_payload=payload,
            response_payload=None,
            error_message=str(exc) or "Dify request timeout",
            latency_ms=None,
            started_at=started,
            finished_at=finished,
        )
    except Exception as exc:
        finished = datetime.utcnow()
        return DifyResult(
            status=RunStatus.DIFY_ERROR,
            http_status=None,
            request_payload=payload,
            response_payload=None,
            error_message=str(exc),
            latency_ms=None,
            started_at=started,
            finished_at=finished,
        )


def _safe_json(response: httpx.Response) -> dict[str, Any] | None:
    try:
        return response.json()
    except Exception:
        return None
