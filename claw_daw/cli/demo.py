from __future__ import annotations

from claw_daw.util.resources import read_text_resource


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
    return read_text_resource(templates[style])
