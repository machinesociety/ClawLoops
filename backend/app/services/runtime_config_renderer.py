from __future__ import annotations

import json
from pathlib import Path

from app.domain.runtime_ports import ModelConfig
from app.schemas.runtime import RuntimeBindingSnapshot


class RuntimeConfigRenderer:
    """
    负责将模型网关配置与 runtime 绑定信息渲染为配置文件和 secret file。
    """

    def __init__(
        self,
        base_dir: str = "/var/lib/clawloops",
    ) -> None:
        self._base_dir = Path(base_dir)

    def render(
        self,
        user_id: str,
        binding: RuntimeBindingSnapshot,
        model_config: ModelConfig,
    ) -> tuple[str, str]:
        """
        渲染配置文件和 secret file，返回它们在宿主机上的路径。
        """
        config_dir = self._base_dir / "runtime-configs" / user_id
        secrets_dir = self._base_dir / "runtime-secrets" / user_id
        config_dir.mkdir(parents=True, exist_ok=True)
        secrets_dir.mkdir(parents=True, exist_ok=True)

        config_path = config_dir / "model-gateway.json"
        secret_path = secrets_dir / "gateway.token"

        config_payload = {
            "baseUrl": model_config.base_url,
            "models": model_config.models,
            "configRenderVersion": model_config.config_render_version,
            "runtimeId": binding.runtimeId,
        }
        config_path.write_text(json.dumps(config_payload), encoding="utf-8")

        # 这里不直接写入真实 token，仅使用内部引用，后续可接入真正的密钥管理。
        secret_payload = {
            "gatewayAccessTokenRef": model_config.gateway_access_token_ref,
        }
        secret_path.write_text(json.dumps(secret_payload), encoding="utf-8")

        return str(config_path), str(secret_path)

