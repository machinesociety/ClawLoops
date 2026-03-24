"""
与 runtime-manager 通信的 HTTP 客户端。
"""

from __future__ import annotations

from typing import Any

import httpx


class RuntimeManagerClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(10.0, connect=5.0)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as client:
            response = client.post(path, json=payload)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("runtime-manager response is not a JSON object")
        return data

    def ensure_running(self, payload: dict) -> dict:
        return self._post("/internal/runtime-manager/containers/ensure-running", payload)

    def stop(self, user_id: str, runtime_id: str) -> Any:
        return self._post(
            "/internal/runtime-manager/containers/stop",
            {"userId": user_id, "runtimeId": runtime_id},
        )

    def delete(self, user_id: str, runtime_id: str, retention_policy: str) -> Any:
        return self._post(
            "/internal/runtime-manager/containers/delete",
            {
                "userId": user_id,
                "runtimeId": runtime_id,
                "retentionPolicy": retention_policy,
            },
        )

