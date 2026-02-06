from __future__ import annotations

import sys
from pathlib import Path


def ensure_repo_on_path() -> Path:
    """Ensure repo root is on sys.path for local tool scripts."""
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root
