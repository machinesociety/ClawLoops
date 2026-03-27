from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    runtime_manager_host: str = "0.0.0.0"
    runtime_manager_port: int = 18080
    runtime_openclaw_network: str = "clawloops_shared"
    runtime_openclaw_image_ref: str = (
        "ghcr.io/openclaw/openclaw@sha256:a5a4c83b773aca85a8ba99cf155f09afa33946c0aa5cc6a9ccb6162738b5da02"
    )
    runtime_openclaw_command: str = "node dist/index.js gateway --bind lan --port 18789"
    runtime_startup_grace_seconds: int = 30
    runtime_startup_poll_seconds: int = 1
    runtime_startup_consecutive_successes: int = 3
    runtime_startup_port: int = 18789

    class Config:
        env_prefix = ""
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
