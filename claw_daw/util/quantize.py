from __future__ import annotations

from dataclasses import dataclass

from claw_daw.model.types import Project


@dataclass
class QuantizeParams:
    grid_ticks: int
    strength: float = 1.0


def parse_grid(ppq: int, token: str) -> int:
    """Parse a grid token into ticks.

    Supported:
      - 4, 8, 16, 32 (note division)
      - "1/4", "1/8", "1/16", ...
      - "beat" -> quarter note
    """
    t = token.strip().lower()
    if t == "beat":
        return ppq
    if t.startswith("1/"):
        denom = int(t.split("/", 1)[1])
    else:
        denom = int(t)
    if denom <= 0:
        raise ValueError("grid must be > 0")
    # quarter note is /4
    return int(ppq * 4 / denom)


def quantize_project_track(project: Project, track_index: int, grid_ticks: int, strength: float = 1.0) -> int:
    if not (0.0 <= strength <= 1.0):
        raise ValueError("strength must be 0..1")
    track = project.tracks[track_index]
    changed = 0
    for i, n in enumerate(list(track.notes)):
        q = round(n.start / grid_ticks) * grid_ticks
        new_start = int(n.start + (q - n.start) * strength)
        if new_start != n.start:
            track.notes.remove(n)
            track.notes.append(type(n)(start=new_start, duration=n.duration, pitch=n.pitch, velocity=n.velocity))
            changed += 1
    if changed:
        project.dirty = True
    return changed
