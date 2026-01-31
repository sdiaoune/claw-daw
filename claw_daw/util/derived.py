from __future__ import annotations

from claw_daw.model.types import Project


def project_song_end_tick(project: Project) -> int:
    end_tick = 0
    for t in project.tracks:
        # arrangement
        if t.clips and t.patterns:
            for c in t.clips:
                pat = t.patterns.get(c.pattern)
                if not pat:
                    continue
                end_tick = max(end_tick, c.start + c.repeats * pat.length)
        # legacy notes
        for n in t.notes:
            end_tick = max(end_tick, n.end)
    return int(end_tick)


def song_length_seconds(project: Project, end_tick: int | None = None) -> float:
    end_tick = project_song_end_tick(project) if end_tick is None else end_tick
    ticks_per_second = (project.tempo_bpm / 60.0) * project.ppq
    if ticks_per_second <= 0:
        return 0.0
    return float(end_tick) / ticks_per_second


def bars_estimate(project: Project, end_tick: int | None = None) -> float:
    end_tick = project_song_end_tick(project) if end_tick is None else end_tick
    ticks_per_bar = project.ppq * 4
    if ticks_per_bar <= 0:
        return 0.0
    return float(end_tick) / ticks_per_bar
