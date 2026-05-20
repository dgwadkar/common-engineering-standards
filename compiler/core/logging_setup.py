"""Structured JSON logging for the compiler.

Phase 4 deliverable per `docs/02-implementation-plan.md` §7 task 7.

The compiler emits structured logs so a release run's output is machine-readable in CI logs and
in the eventual ``release.yml`` workflow (Phase 7). Each line is a single JSON object on its
own line. Sample:

    {"ts":"2026-05-18T18:41:02.001Z","level":"INFO","event":"emit","stack":"java-spring-boot-3",
     "target":"cursor","rule_id":"java-spring-controller-dto-record-mandate",
     "output_path":"dist/stacks/java-spring-boot-3/cursor/rules/dto-record-mandate.mdc",
     "bytes":4321}

The schema is intentionally minimal:

* ``ts`` — ISO-8601 UTC timestamp, millisecond precision.
* ``level`` — INFO | WARN | ERROR.
* ``event`` — short event name; the rest of the fields are event-specific.

All compiler modules go through this single API so future Phase-5/Phase-7 additions inherit
the same format without rewiring.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Optional


class _JsonFormatter(logging.Formatter):
    """Renders a logging.LogRecord as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.%f"
            )[:-3]
            + "Z",
            "level": record.levelname,
            "event": getattr(record, "event", record.getMessage()),
        }
        for key, value in record.__dict__.items():
            if key in payload or key in _STANDARD_LOGRECORD_FIELDS:
                continue
            payload[key] = value
        return json.dumps(payload, sort_keys=False, ensure_ascii=False)


# Names defined on every LogRecord that we don't want to copy through to the JSON output.
_STANDARD_LOGRECORD_FIELDS = {
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


def get_logger(name: str = "compiler", *, stream=sys.stderr, level: int = logging.INFO) -> logging.Logger:
    """Returns a singleton logger emitting JSON lines to ``stream`` (default stderr).

    Idempotent — calling twice with the same name returns the same logger without doubling
    handlers. Tests can pass a custom ``stream`` (e.g., ``io.StringIO``) to capture output.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    for h in logger.handlers:
        if getattr(h, "_compiler_json", False) and getattr(h, "_stream_id", None) == id(stream):
            return logger

    # Replace any older compiler handlers (e.g., from a previous get_logger call with a different
    # stream) to avoid double-emission in test runs.
    logger.handlers = [h for h in logger.handlers if not getattr(h, "_compiler_json", False)]

    handler = logging.StreamHandler(stream)
    handler.setFormatter(_JsonFormatter())
    handler._compiler_json = True  # type: ignore[attr-defined]
    handler._stream_id = id(stream)  # type: ignore[attr-defined]
    logger.addHandler(handler)
    return logger


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, /, **fields: Any) -> None:
    """Emits one structured event line.

    Example::

        log_event(logger, "emit", stack="java-spring-boot-3", target="cursor",
                  rule_id="dto-record-mandate", output_path="dist/...", bytes=4321)
    """
    logger.log(level, event, extra={"event": event, **fields})


__all__ = ["get_logger", "log_event"]
