"""Gunicorn configuration — applies unified log formatting to master and workers."""

from __future__ import annotations

import logging
import logging.config

import gunicorn.glogging

from lunchmoney_mcp.logging_config import LOG_CONFIG

bind = "0.0.0.0:8000"
worker_class = "uvicorn_worker.UvicornWorker"

_GUNICORN_LOGGERS = ("gunicorn.error", "gunicorn.access")


class _UnifiedLogger(gunicorn.glogging.Logger):
    """Gunicorn Logger whose every instantiation applies the unified log format."""

    def __init__(self, cfg: object) -> None:
        super().__init__(cfg)
        for name in _GUNICORN_LOGGERS:
            logging.getLogger(name).handlers.clear()
        logging.config.dictConfig(LOG_CONFIG)


logger_class = _UnifiedLogger
