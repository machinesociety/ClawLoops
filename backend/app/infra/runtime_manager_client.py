"""
与 runtime-manager 通信的 HTTP 客户端占位。

TODO:
- 使用 httpx 或 requests 实现真实调用。
- 从配置读取 runtime-manager 基础地址。
"""

from typing import Any


class RuntimeManagerClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    def ensure_running(self, payload: dict) -> dict:
        """
        发送 ensure-running 请求的占位实现。
        """

        _ = payload
        return {
            "runtimeId": "rt_001",
            "observedState": "creating",
            "internalEndpoint": "http://clawloops-u001:3000",
            "message": "creating",
        }

    def stop(self, runtime_id: str) -> Any:
        _ = runtime_id
        return {"status": "accepted"}

    def delete(self, runtime_id: str) -> Any:
        _ = runtime_id
        return {"status": "accepted"}

