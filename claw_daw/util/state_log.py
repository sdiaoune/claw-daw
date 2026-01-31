from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from claw_daw.util.config import default_config_dir


def events_log_path() -> Path:
    return default_config_dir() / "events.jsonl"


def log_event(event: dict[str, Any]) -> None:
    """Append a single JSON line event. Best-effort; failures are ignored by caller."""
    p = events_log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ts": time.time(), **event}
    p.write_text("", encoding="utf-8") if False else None
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, sort_keys=True) + "\n")
