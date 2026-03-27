from __future__ import annotations

from app.domain.runtime_ports import ModelConfig
from app.schemas.runtime import RuntimeBindingSnapshot


class RuntimeConfigRenderer:
    """
    负责渲染 RuntimeManager V2.2 所需的完整 openclaw.json。
    """

    def render(
        self,
        user_id: str,
        binding: RuntimeBindingSnapshot,
        model_config: ModelConfig,
    ) -> tuple[dict, str]:
        """
        返回 openclaw.json 与 configVersion。
        """
        openclaw_json = {
            "auth": {
                "profiles": {
                    "litellm:default": {
                        "provider": "litellm",
                        "mode": "api_key",
                    }
                }
            },
            "gateway": {
                "bind": "lan",
                "port": 18789,
                "mode": "local",
                "auth": {
                    "mode": "token",
                    # V2.2 中 token 由后端渲染结果下发；此处先以可替换引用占位。
                    "token": model_config.gateway_access_token_ref,
                },
            },
            "models": {
                "providers": {
                    "litellm": {
                        "baseUrl": model_config.base_url,
                        "apiKey": "not_empty",
                        "api": "openai-completions",
                        "models": [
                            {
                                "id": model_id,
                                "name": model_id,
                                "reasoning": False,
                                "input": ["text"],
                                "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                                "contextWindow": 128000,
                                "maxTokens": 8192,
                            }
                            for model_id in model_config.models
                        ],
                    }
                },
                "mode": "merge",
            },
            "runtime": {
                "runtimeId": binding.runtimeId,
                "userId": user_id,
            },
            "agents": {
                "defaults": {
                    "model": {
                        "primary": f"litellm/{model_config.models[0]}" if model_config.models else "litellm/default",
                    }
                },
                "list": [{"id": "main", "model": f"litellm/{model_config.models[0]}"}]
                if model_config.models
                else [],
            },
        }
        return openclaw_json, model_config.config_render_version

