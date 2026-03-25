from datetime import UTC, datetime
from typing import Any

import httpx

from app.models.target import Target


class TargetClientError(Exception):
    def __init__(self, error_type: str, error_message: str, latency_ms: int) -> None:
        self.error_type = error_type
        self.error_message = error_message
        self.latency_ms = latency_ms
        super().__init__(error_message)


def invoke_target(
    target: Target, *, task_type: str, input_json: dict[str, Any]
) -> tuple[dict[str, Any], int]:
    url = build_target_url(target)
    started = datetime.now(UTC)

    try:
        response = httpx.post(
            url,
            json={"task_type": task_type, "input": input_json},
            headers=target.headers_json,
            timeout=target.timeout_ms / 1000,
        )
        latency_ms = _elapsed_latency_ms(started)
        response.raise_for_status()
        return response.json(), latency_ms
    except httpx.TimeoutException as exc:
        raise TargetClientError(
            "timeout", str(exc), _elapsed_latency_ms(started)
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise TargetClientError(
            "http_status_error",
            f"Target returned status {exc.response.status_code}",
            _elapsed_latency_ms(started),
        ) from exc
    except httpx.HTTPError as exc:
        raise TargetClientError(
            "http_error", str(exc), _elapsed_latency_ms(started)
        ) from exc
    except ValueError as exc:
        raise TargetClientError(
            "invalid_json", str(exc), _elapsed_latency_ms(started)
        ) from exc


def build_target_url(target: Target) -> str:
    return f"{target.base_url.rstrip('/')}/{target.endpoint_path.lstrip('/')}"


def _elapsed_latency_ms(started: datetime) -> int:
    return int((datetime.now(UTC) - started).total_seconds() * 1000)
