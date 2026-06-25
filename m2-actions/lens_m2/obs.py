"""Observability primitives: a request-scoped correlation id + JSON logging.

One id per request is generated (or taken from an inbound ``X-Correlation-ID``)
and propagated — via a context variable — to both the structured logs and the
audit trail, so a single action can be traced end to end across them. Minimal and
dependency-free; the point is to demonstrate the *practice*, not ship an APM.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from contextvars import ContextVar
from uuid import uuid4

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def new_correlation_id() -> str:
    """Start a fresh trace and make it current for this context."""
    cid = uuid4().hex
    _correlation_id.set(cid)
    return cid


def set_correlation_id(cid: str) -> None:
    _correlation_id.set(cid)


def correlation_id() -> str:
    """Current trace id, generating one if none is set (e.g. a non-HTTP caller)."""
    cid = _correlation_id.get()
    if not cid:
        cid = uuid4().hex
        _correlation_id.set(cid)
    return cid


class JsonFormatter(logging.Formatter):
    """Render each log record as a single structured JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "correlation_id": _correlation_id.get(),
        }
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, sort_keys=True, default=str)


def get_logger(name: str) -> logging.Logger:
    """A logger that emits structured JSON to stderr (idempotent setup)."""
    logger = logging.getLogger(name)
    if not any(isinstance(h.formatter, JsonFormatter) for h in logger.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def log(logger: logging.Logger, msg: str, *, level: int = logging.INFO, **fields: object) -> None:
    """Emit a structured log line with arbitrary key/value fields."""
    logger.log(level, msg, extra={"fields": fields})
