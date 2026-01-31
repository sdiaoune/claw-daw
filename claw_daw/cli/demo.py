from __future__ import annotations

from pathlib import Path


def demo_script_text(style: str) -> str:
    style = style.lower()
    templates = {
        "hiphop": "templates/hiphop_1min.txt",
        "trap": "templates/trap_1min.txt",
        "lofi": "templates/lofi_1min.txt",
        "house": "templates/house_1min.txt",
    }
    if style not in templates:
        raise ValueError("style must be one of: hiphop, trap, lofi, house")
    return Path(templates[style]).read_text(encoding="utf-8")
