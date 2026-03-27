from functools import lru_cache

from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """应用基础配置，占位用于后续按环境扩展。"""

    env: str = "dev"
    log_level: str = "INFO"

    # 轻量认证（server-side session）
    session_cookie_name: str = "clawloops_session"
    session_ttl_seconds: int = 60 * 60 * 24 * 7  # 7 days
    cookie_secure: bool = False
    cookie_samesite: str = "lax"  # "lax" | "strict" | "none"
    cookie_domain: str | None = None

    # 兼容保留：旧 Authentik 头/跳转配置（v0.12 不再使用）
    auth_header_subject: str = "X-Authentik-Subject"
    auth_header_email: str = "X-Authentik-Email"
    auth_header_groups: str = "X-Authentik-Groups"
    authentik_public_url: str = "http://localhost:9000"
    auth_post_login_redirect_url: str = "http://clawloops.localhost/post-login"

    # 预留后续接入的外部服务配置字段
    database_url: str | None = None
    runtime_manager_base_url: str | None = None
    route_host_suffix: str = "clawloops.localhost"
    model_gateway_base_url: str | None = None
    model_gateway_default_models: str = "qwen-max-proxy"
    litellm_api_key: str = "sk-local-master"

    def get_model_gateway_default_models(self) -> list[str]:
        models = [item.strip() for item in self.model_gateway_default_models.split(",")]
        return [item for item in models if item]

    class Config:
        env_prefix = "CLAWLOOPS_"
        case_sensitive = False


@lru_cache
def get_settings() -> AppSettings:
    """提供带缓存的全局配置实例，供依赖注入使用。"""

    return AppSettings()

