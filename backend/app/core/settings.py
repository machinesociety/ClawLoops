from functools import lru_cache

from pydantic import BaseSettings


class AppSettings(BaseSettings):
    """应用基础配置，占位用于后续按环境扩展。"""

    env: str = "dev"
    log_level: str = "INFO"

    # 预留后续接入的外部服务配置字段
    database_url: str | None = None
    runtime_manager_base_url: str | None = None
    model_gateway_base_url: str | None = None

    class Config:
        env_prefix = "CREWCLAW_"
        case_sensitive = False


@lru_cache
def get_settings() -> AppSettings:
    """提供带缓存的全局配置实例，供依赖注入使用。"""

    return AppSettings()

