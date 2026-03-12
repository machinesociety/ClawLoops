import logging
from logging.config import dictConfig

from app.core.settings import AppSettings


def setup_logging(settings: AppSettings) -> None:
    """根据配置初始化应用日志（结构化友好，可后续接入集中日志）。"""

    log_level = settings.log_level.upper()

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
                },
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                },
            },
            "root": {
                "level": log_level,
                "handlers": ["default"],
            },
        }
    )

    logging.getLogger(__name__).info("Logging configured", extra={"env": settings.env})

