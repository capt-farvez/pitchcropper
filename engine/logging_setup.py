"""Structured logging for unattended runs.

One JSON object per line on stdout. Every record carries the run id, a
timestamp, a level and an event name, plus whatever fields the caller
attached. An operator can grep a run out of a batch log by id, watch progress
records to see it moving, and read the last record to know how it ended.
"""

import json
import logging
import sys
import time
import uuid

_STANDARD_ATTRS = set(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "event": record.getMessage(),
            "logger": record.name,
        }
        # anything passed via extra={...} becomes a top-level field
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class TextFormatter(logging.Formatter):
    """One readable line per record: time, level, event, then key=value fields."""

    def format(self, record: logging.LogRecord) -> str:
        fields = " ".join(
            f"{key}={value}"
            for key, value in record.__dict__.items()
            if key not in _STANDARD_ATTRS and not key.startswith("_") and key != "run_id"
        )
        line = f"{time.strftime('%H:%M:%S', time.localtime(record.created))} {record.levelname:<7} {record.getMessage():<18} {fields}".rstrip()
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


class RunIdFilter(logging.Filter):
    def __init__(self, run_id: str):
        super().__init__()
        self.run_id = run_id

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = self.run_id
        return True


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def configure_logging(level: str, run_id: str, fmt: str = "json") -> None:
    """Route the engine's loggers to stdout, tagged with the run id.

    fmt "json" gives one JSON object per line for batch environments and log
    collectors. fmt "text" gives one readable line per record for a person at
    a terminal.
    """
    root = logging.getLogger("engine")
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(TextFormatter() if fmt == "text" else JsonFormatter())
    # the filter sits on the handler, not the logger: logger filters do not
    # run for records propagated up from child loggers like engine.analyzer
    handler.addFilter(RunIdFilter(run_id))
    root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False
