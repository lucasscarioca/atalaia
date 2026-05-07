from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass(slots=True)
class HTTPAdapter:
    base_url: str
    path: str
    timeout_ms: int = 10_000
    headers: dict[str, str] = field(default_factory=dict)
    method: str = "POST"

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/{self.path.lstrip('/')}"
        with httpx.Client(timeout=self.timeout_ms / 1000, headers=self.headers) as client:
            response = client.request(self.method.upper(), url, json={"input": payload})
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise TypeError("HTTP adapter expected a JSON object response")
            return data
