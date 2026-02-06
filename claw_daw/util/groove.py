from __future__ import annotations

from dataclasses import dataclass
from random import Random

from claw_daw.model.types import Note


@dataclass(frozen=True)
class HumanizeSettings:
    timing_ticks: int = 0  # max +/- tick jitter
    velocity: int = 0  # max +/- velocity jitter
    seed: int = 0


def humanize_notes(notes: list[Note], *, settings: HumanizeSettings) -> list[Note]:
    """Return new notes list with deterministic humanization.

    This is intentionally simple and safe:
    - Never makes start negative
    - Keeps duration unchanged
    - Clamps velocity to [1,127]
    """

    if settings.timing_ticks <= 0 and settings.velocity <= 0:
        return [
            Note(
                start=n.start,
                duration=n.duration,
                pitch=n.pitch,
                velocity=n.velocity,
                role=getattr(n, "role", None),
                chance=getattr(n, "chance", 1.0),
                mute=getattr(n, "mute", False),
                accent=getattr(n, "accent", 1.0),
                glide_ticks=getattr(n, "glide_ticks", 0),
            )
            for n in notes
        ]

    rnd = Random(int(settings.seed))
    out: list[Note] = []
    for n in notes:
        dt = rnd.randint(-int(settings.timing_ticks), int(settings.timing_ticks)) if settings.timing_ticks > 0 else 0
        dv = rnd.randint(-int(settings.velocity), int(settings.velocity)) if settings.velocity > 0 else 0
        start = max(0, int(n.start) + dt)
        vel = max(1, min(127, int(n.velocity) + dv))
        out.append(
            Note(
                start=start,
                duration=int(n.duration),
                pitch=int(n.pitch),
                velocity=vel,
                role=getattr(n, "role", None),
                chance=getattr(n, "chance", 1.0),
                mute=getattr(n, "mute", False),
                accent=getattr(n, "accent", 1.0),
                glide_ticks=getattr(n, "glide_ticks", 0),
            )
        )
    out.sort(key=lambda x: (x.start, x.pitch))
    return out
