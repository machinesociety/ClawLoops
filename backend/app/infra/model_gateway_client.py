"""
与 LiteLLM / ClawLoops 模型网关交互的客户端占位。

TODO:
- 根据实际接口获取用户可用模型与 gateway-config。
"""

from typing import Any


class ModelGatewayClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    def get_user_model_config(self, user_id: str) -> dict[str, Any]:
        _ = user_id
        return {
            "baseUrl": self._base_url,
            "models": ["gpt-4-mini"],
            "gatewayAccessTokenRef": "token_ref_001",
            "configRenderVersion": "v1",
        }

