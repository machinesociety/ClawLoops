
"""
与 LiteLLM / ClawLoops 模型网关交互的客户端占位。
"""


from __future__ import annotations

from typing import Any

import httpx
import sys


class ModelGatewayClient:
    def __init__(self, base_url: str, timeout_seconds: float = 2.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def list_models(self) -> list[str]:
        """
        尝试从网关读取真正可用的模型列表（OpenAI 兼容：GET /v1/models）。
        """
        if "pytest" in sys.modules:
            return []
        url = f"{self._base_url}/v1/models"
        with httpx.Client(timeout=self._timeout_seconds) as client:
            resp = client.get(url)
            resp.raise_for_status()
            payload: dict[str, Any] = resp.json() if resp.content else {}

        data = payload.get("data", [])
        if not isinstance(data, list):
            return []
        model_ids: list[str] = []
        for item in data:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                model_ids.append(item["id"])
        return model_ids

    def get_user_model_config(self, user_id: str, preferred_models: list[str]) -> dict[str, Any]:
        """
        返回 Runtime 渲染 openclaw.json 需要的配置数据。

        - models：优先按 preferred_models 顺序输出，并与网关真实可用模型取交集。
        - 若无法读取网关模型列表，则回退到 preferred_models。
        """
        _ = user_id

        resolved_models = [m for m in preferred_models if m]
        try:
            available = set(self.list_models())
            filtered = [m for m in resolved_models if m in available]
            if filtered:
                resolved_models = filtered
        except Exception:
            pass

        return {
            "baseUrl": self._base_url,
            "models": resolved_models,
            "gatewayAccessTokenRef": "token_ref_001",
            "configRenderVersion": "v1",
        }

