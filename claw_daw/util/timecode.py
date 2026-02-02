from __future__ import annotations

from claw_daw.model.types import Project


def parse_timecode_ticks(project: Project, value: str | int) -> int:
    """Parse time strings into ticks.

    Supported:
    - integer ticks ("960" or 960)
    - bar:beat ("2:0" means bar 2, beat 0) in 4/4
    - bar:beat:tick ("2:0:120")

    Bars and beats are 0-indexed.
    """

    if isinstance(value, int):
        return int(value)

    s = str(value).strip()
    if not s:
        raise ValueError("empty timecode")

    if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
        return int(s)

    parts = s.split(":")
    if len(parts) not in {2, 3}:
        raise ValueError(f"invalid timecode: {value}")

    bar = int(parts[0])
    beat = int(parts[1])
    sub = int(parts[2]) if len(parts) == 3 else 0
    if bar < 0 or beat < 0 or sub < 0:
        raise ValueError("timecode must be >= 0")

    ticks_per_bar = int(project.ppq) * 4
    ticks_per_beat = int(project.ppq)

    return bar * ticks_per_bar + beat * ticks_per_beat + sub
