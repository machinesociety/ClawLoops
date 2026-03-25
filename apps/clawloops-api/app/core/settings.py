from functools import lru_cache

from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """应用基础配置，占位用于后续按环境扩展。"""

    env: str = "dev"
    log_level: str = "INFO"

    # Authentik / 认证相关头部配置
    auth_header_subject: str = "X-authentik-uid"
    auth_header_email: str = "X-Authentik-Email"
    auth_header_groups: str = "X-Authentik-Groups"
    authentik_public_url: str = "http://localhost:9000"
    auth_post_login_redirect_url: str = "http://clawloops.localhost/post-login"

    # 预留后续接入的外部服务配置字段
    database_url: str | None = None
    runtime_manager_base_url: str | None = None
    route_host_suffix: str = "clawloops.localhost"
    model_gateway_base_url: str | None = None

    class Config:
        env_prefix = "CLAWLOOPS_"
        case_sensitive = False


@lru_cache
def get_settings() -> AppSettings:
    """提供带缓存的全局配置实例，供依赖注入使用。"""

    return AppSettings()

