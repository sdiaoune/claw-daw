from __future__ import annotations

import re

from claw_daw.prompt.types import Brief, StyleName


_STYLE_WORDS: list[tuple[StyleName, list[str]]] = [
    ("hiphop", ["hiphop", "hip-hop", "trap", "boom bap", "boom-bap"]),
    ("lofi", ["lofi", "lo-fi", "lo fi", "chillhop", "chill-hop"]),
    ("house", ["house", "deep house", "garage"]),
    ("techno", ["techno", "industrial", "rave"]),
    ("ambient", ["ambient", "drone"]),
]


def _guess_style(p: str) -> StyleName:
    s = p.lower()
    for style, words in _STYLE_WORDS:
        for w in words:
            if w in s:
                return style
    return "unknown"


def _guess_bpm(p: str) -> int | None:
    # Accept: "BPM: 74", "74bpm", "tempo 120".
    m = re.search(r"\b(bpm|tempo)\s*[:=]?\s*(\d{2,3})\b", p, flags=re.I)
    if m:
        return int(m.group(2))

    m2 = re.search(r"\b(\d{2,3})\s*bpm\b", p, flags=re.I)
    if m2:
        return int(m2.group(1))

    return None


def _guess_key(p: str) -> str | None:
    # Very lightweight; keep as string.
    m = re.search(r"\bkey\s*[:=]?\s*([A-Ga-g])\s*(#|b)?\s*(major|minor|maj|min)?\b", p)
    if not m:
        return None
    note = m.group(1).upper()
    accidental = m.group(2) or ""
    mode = (m.group(3) or "").lower()
    if mode in {"min", "minor"}:
        mode = "minor"
    elif mode in {"maj", "major"}:
        mode = "major"
    return f"{note}{accidental} {mode}".strip()


def _guess_length_bars(p: str) -> int | None:
    # Accept explicit bars: "24 bars", "Intro: 8 bars"; we pick a total if present.
    m = re.search(r"\b(total\s*)?(\d{1,3})\s*bars\b", p, flags=re.I)
    if m:
        n = int(m.group(2))
        if 4 <= n <= 256:
            return n
    return None


def parse_prompt(prompt: str, *, title: str | None = None) -> Brief:
    """Parse a natural-language prompt into a structured Brief.

    This is an intentionally offline heuristic parser. The goal is:
    - stable behavior
    - easy-to-test logic
    - good defaults
    """

    p = (prompt or "").strip()
    b = Brief(prompt=p)

    if title:
        b.title = title
    else:
        # Use first line, sanitized a bit.
        first = p.splitlines()[0] if p else "untitled"
        b.title = first.strip()[:80] or "untitled"

    b.style = _guess_style(p)
    b.bpm = _guess_bpm(p)
    b.key = _guess_key(p)

    # Mood: just grab some common words.
    pl = p.lower()
    for w in ["dark", "bright", "moody", "chill", "aggressive", "uplifting", "sad", "happy"]:
        if w in pl:
            b.mood = w
            break

    lb = _guess_length_bars(p)
    if lb is not None:
        b.length_bars = lb

    return b
