from __future__ import annotations

from dataclasses import dataclass

from claw_daw.model.types import Project


@dataclass(frozen=True)
class AcceptanceFailure(Exception):
    errors: list[str]

    def __str__(self) -> str:  # pragma: no cover
        return "AcceptanceFailure:\n- " + "\n- ".join(self.errors)


def require(
    cond: bool,
    msg: str,
    errors: list[str],
) -> None:
    if not cond:
        errors.append(msg)


def track_index_by_name(proj: Project, name_lower: str) -> int | None:
    for i, t in enumerate(proj.tracks):
        if t.name.strip().lower() == name_lower:
            return i
    return None


def pattern_note_count(proj: Project, track_i: int, pattern: str) -> int:
    t = proj.tracks[track_i]
    pat = t.patterns.get(pattern)
    if not pat:
        return 0
    return sum(1 for n in pat.notes if not getattr(n, "mute", False) and float(getattr(n, "chance", 1.0)) > 0.0)


def pattern_has_pitch_near_step(
    proj: Project,
    track_i: int,
    pattern: str,
    *,
    pitch: int,
    step_index: int,
    step_count: int,
    tol_steps: int = 0,
) -> bool:
    """Best-effort check: is there a note of pitch at a given 16th-step index (mod pattern)?"""

    t = proj.tracks[track_i]
    pat = t.patterns.get(pattern)
    if not pat:
        return False

    step = max(1, int(proj.ppq) // 4)
    target = int(step_index) % int(step_count)

    for n in pat.notes:
        if int(n.pitch) != int(pitch):
            continue
        s = (int(n.start) // step) % int(step_count)
        if abs(s - target) <= int(tol_steps):
            return True
    return False
