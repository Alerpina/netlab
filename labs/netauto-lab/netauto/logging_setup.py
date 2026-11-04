"""Logs em JSON com run_id e commit: toda ação fica rastreável até a mudança que a causou."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from functools import cache
from pathlib import Path

_STANDARD = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


@cache
def run_context() -> dict[str, str]:
    run_id = os.getenv("RUN_ID") or os.getenv("GITHUB_RUN_ID") or uuid.uuid4().hex[:12]
    commit = os.getenv("GITHUB_SHA", "")
    if not commit:
        try:
            commit = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            commit = "unknown"
    return {"run_id": run_id, "commit": commit[:12]}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="seconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            **run_context(),
        }
        payload.update({k: v for k, v in record.__dict__.items() if k not in _STANDARD})
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def get_logger(name: str = "netauto", log_dir: Path | None = None) -> logging.Logger:
    root = logging.getLogger("netauto")
    if not root.handlers:
        root.setLevel(os.getenv("LOG_LEVEL", "INFO"))
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(JsonFormatter())
        root.addHandler(stream)
        if log_dir is not None:
            log_dir.mkdir(parents=True, exist_ok=True)
            file = logging.FileHandler(log_dir / f"{run_context()['run_id']}.jsonl")
            file.setFormatter(JsonFormatter())
            root.addHandler(file)
    return logging.getLogger(name if name.startswith("netauto") else f"netauto.{name}")
