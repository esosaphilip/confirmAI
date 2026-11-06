"""Strukturiertes Logging fuer confirmAI.

Jede Zeile ist ein JSON-Objekt mit Zeitstempel, Level, Logger, Nachricht,
der aktuellen ``run_id`` und frei waehlbaren Feldern, die per
``logger.info("...", extra={"fields": {...}})`` angehaengt werden.

Mit ``CONFIRMAI_LOG_FORMAT=text`` gibt es stattdessen gut lesbare Zeilen
fuer die lokale Entwicklung. ``CONFIRMAI_LOG_LEVEL`` setzt das Level.
"""

from __future__ import annotations

import json
import logging
import os
from contextvars import ContextVar
from datetime import datetime, timezone

run_id_var: ContextVar[str] = ContextVar("run_id", default="-")


class _RunIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = run_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "run_id": getattr(record, "run_id", "-"),
            "msg": record.getMessage(),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload.update(fields)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = (
            f"{self.formatTime(record, '%H:%M:%S')} {record.levelname:<7} "
            f"[{getattr(record, 'run_id', '-')}] {record.name}: {record.getMessage()}"
        )
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict) and fields:
            base += " " + " ".join(f"{k}={v}" for k, v in fields.items())
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


_configured = False


def configure_logging() -> None:
    """Richtet den Root-Logger einmalig ein (idempotent)."""
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler()
    handler.addFilter(_RunIdFilter())
    fmt = os.getenv("CONFIRMAI_LOG_FORMAT", "json").lower()
    handler.setFormatter(TextFormatter() if fmt == "text" else JsonFormatter())

    root = logging.getLogger("confirmai")
    root.setLevel(os.getenv("CONFIRMAI_LOG_LEVEL", "INFO").upper())
    root.addHandler(handler)
    root.propagate = False
    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"confirmai.{name}")
