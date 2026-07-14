"""Application logging setup."""

from __future__ import annotations

from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any
import json
import logging
import sys

from content_engine.config import LoggingSettings


LOGGER_NAME = "content_engine"


class JsonFormatter(logging.Formatter):
    """Small structured formatter for console and file logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in _STANDARD_LOG_RECORD_KEYS:
                continue
            payload[key] = value
        return json.dumps(payload, default=str, sort_keys=True)


def configure_logging(settings: LoggingSettings) -> logging.Logger:
    settings.directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(settings.level)
    logger.handlers.clear()
    logger.propagate = False

    formatter = JsonFormatter()
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(settings.level)
    console.setFormatter(formatter)

    app_file = RotatingFileHandler(
        settings.directory / settings.app_log_name,
        maxBytes=settings.max_bytes,
        backupCount=settings.backup_count,
        encoding="utf-8",
    )
    app_file.setLevel(settings.level)
    app_file.setFormatter(formatter)

    error_file = RotatingFileHandler(
        settings.directory / settings.error_log_name,
        maxBytes=settings.max_bytes,
        backupCount=settings.backup_count,
        encoding="utf-8",
    )
    error_file.setLevel(logging.ERROR)
    error_file.setFormatter(formatter)

    logger.addHandler(console)
    logger.addHandler(app_file)
    logger.addHandler(error_file)
    logger.info("logging_configured", extra={"component": "logging", "log_dir": str(settings.directory)})
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(LOGGER_NAME if name is None else f"{LOGGER_NAME}.{name}")


def expected_log_files(settings: LoggingSettings) -> list[Path]:
    return [settings.directory / settings.app_log_name, settings.directory / settings.error_log_name]


_STANDARD_LOG_RECORD_KEYS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "message",
    "module",
    "msecs",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}
