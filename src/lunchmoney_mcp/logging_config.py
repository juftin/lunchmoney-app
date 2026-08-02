"""Unified logging configuration for dev (uvicorn) and prod (Gunicorn) runtimes."""

from __future__ import annotations

import logging
import logging.config
import sys
from copy import copy, deepcopy
from typing import Any, Literal

import uvicorn.config
from uvicorn.config import LOGGING_CONFIG as _UVICORN_LOGGING_CONFIG


class _DefaultFormatter(logging.Formatter):
    """Log formatter with colored level name and colored logger name."""

    _LEVEL_COLORS: dict[str, str] = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[91m",
    }
    _NAME_COLOR: str = "\033[35m"
    _RESET: str = "\033[0m"
    _LEVEL_WIDTH: int = 8

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        style: Literal["%", "{", "$"] = "%",
        use_colors: bool | None = None,
    ) -> None:
        self.use_colors = (
            use_colors if use_colors is not None else sys.stderr.isatty()
        )
        super().__init__(fmt=fmt, datefmt=datefmt, style=style)

    def formatMessage(self, record: logging.LogRecord) -> str:
        recordcopy = copy(record)
        if self.use_colors:
            color = self._LEVEL_COLORS.get(recordcopy.levelname, "")
            padded = f"{recordcopy.levelname:>{self._LEVEL_WIDTH}}"
            recordcopy.levelname = f"{color}{padded}{self._RESET}"
            recordcopy.name = f"{self._NAME_COLOR}{recordcopy.name}{self._RESET}"
            if "color_message" in recordcopy.__dict__:
                recordcopy.msg = recordcopy.__dict__["color_message"]
                recordcopy.__dict__["message"] = recordcopy.getMessage()
        else:
            recordcopy.levelname = f"{recordcopy.levelname:>{self._LEVEL_WIDTH}}"
        return super().formatMessage(recordcopy)


LOG_CONFIG: dict[str, Any] = deepcopy(_UVICORN_LOGGING_CONFIG)
LOG_CONFIG["formatters"]["default"] = {
    "()": "lunchmoney_mcp.logging_config._DefaultFormatter",
    "fmt": "%(asctime)s [%(levelname)s]: %(message)s [%(name)s]",
    "use_colors": None,
}
LOG_CONFIG["formatters"]["access"]["fmt"] = (
    "%(asctime)s [%(levelprefix)s] %(client_addr)s - "
    '"%(request_line)s" %(status_code)s [%(name)s]'
)
LOG_CONFIG["loggers"][""] = {"handlers": ["default"], "level": "INFO"}
LOG_CONFIG["loggers"]["alembic"] = {
    "handlers": ["default"],
    "level": "INFO",
    "propagate": False,
}
LOG_CONFIG["loggers"]["sqlalchemy.engine"] = {
    "handlers": ["default"],
    "level": "WARN",
    "propagate": False,
}
LOG_CONFIG["loggers"]["gunicorn.error"] = {
    "handlers": ["default"],
    "level": "INFO",
    "propagate": False,
}
LOG_CONFIG["loggers"]["gunicorn.access"] = {
    "handlers": ["default"],
    "level": "INFO",
    "propagate": False,
}


def apply() -> None:
    """Apply unified logging config and patch uvicorn defaults for Gunicorn workers."""
    uvicorn.config.LOGGING_CONFIG = LOG_CONFIG
    logging.config.dictConfig(LOG_CONFIG)


__all__ = ["LOG_CONFIG", "apply"]
