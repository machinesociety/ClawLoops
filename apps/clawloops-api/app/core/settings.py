from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """应用基础配置，占位用于后续按环境扩展。"""

    env: str = "dev"
    log_level: str = "INFO"

    # Authentik / 认证相关头部配置
    auth_header_subject: str = "X-authentik-uid"
    auth_header_email: str = "X-Authentik-Email"
    auth_header_groups: str = "X-Authentik-Groups"
    # 逗号分隔，与 Authentik 中 Group 名称完全一致；命中任一即应用内 UserRole.ADMIN
    # 含 Authentik 内置组名 authentik Admins，便于 akadmin 等与 clawloops-admins 并存
    auth_admin_group_slugs: str = "clawloops-admins,authentik Admins"
    authentik_public_url: str = "http://localhost:9000"
    auth_post_login_redirect_url: str = "http://clawloops.localhost/post-login"
    authentik_enrollment_flow_slug: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            # 文档冻结命名：允许不带前缀的配置
            "AUTHENTIK_ENROLLMENT_FLOW_SLUG",
            # 兼容现有 env_prefix=CLAWLOOPS_ 的习惯用法
            "CLAWLOOPS_AUTHENTIK_ENROLLMENT_FLOW_SLUG",
        ),
    )
    authentik_api_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "AUTHENTIK_API_BASE_URL",
            "CLAWLOOPS_AUTHENTIK_API_BASE_URL",
        ),
    )
    authentik_api_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "AUTHENTIK_API_TOKEN",
            "CLAWLOOPS_AUTHENTIK_API_TOKEN",
        ),
    )

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

