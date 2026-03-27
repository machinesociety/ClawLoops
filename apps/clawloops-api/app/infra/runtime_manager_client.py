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

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as client:
            response = client.request(method, path, json=payload)
        if response.is_error:
            detail = None
            try:
                body = response.json()
                if isinstance(body, dict):
                    detail_obj = body.get("detail")
                    if isinstance(detail_obj, dict):
                        detail = f"{detail_obj.get('code', 'RM_ERROR')}: {detail_obj.get('message', response.text)}"
            except Exception:
                detail = None
            raise RuntimeError(detail or f"runtime-manager request failed: {response.status_code}")
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("runtime-manager response is not a JSON object")
        return data

    def ensure_running(self, payload: dict) -> dict:
        return self._request("POST", "/internal/runtime-manager/containers/ensure-running", payload)

    def stop(self, user_id: str, runtime_id: str) -> Any:
        return self._request(
            "POST",
            "/internal/runtime-manager/containers/stop",
            {"userId": user_id, "runtimeId": runtime_id},
        )

    def delete(
        self,
        user_id: str,
        runtime_id: str,
        retention_policy: str,
        compat: dict[str, str] | None = None,
    ) -> Any:
        payload: dict[str, Any] = {
            "userId": user_id,
            "runtimeId": runtime_id,
            "retentionPolicy": retention_policy,
        }
        if compat is not None:
            payload["compat"] = compat
        return self._request(
            "POST",
            "/internal/runtime-manager/containers/delete",
            payload,
        )

    def get_container(self, runtime_id: str) -> dict[str, Any]:
        return self._request("GET", f"/internal/runtime-manager/containers/{runtime_id}")

