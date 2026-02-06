from __future__ import annotations

from random import Random

from claw_daw.arrange.variations import resolve_pattern_name
from claw_daw.model.types import Note, Project, Track
from claw_daw.util.drumkit import expand_role_notes
from claw_daw.util.groove import HumanizeSettings, humanize_notes


def apply_swing_tick(tick: int, ppq: int, swing_percent: int) -> int:
    """Apply swing to ticks.

    We swing the offbeat 16th (i.e. step = ppq/4, swing odd steps).
    """
    if swing_percent <= 0:
        return tick
    step = ppq // 4
    if step <= 0:
        return tick
    s = tick // step
    if s % 2 == 1:
        offset = int(step * (swing_percent / 100.0))
        return tick + offset
    return tick


def flatten_track_notes(
    project: Project,
    track_index: int,
    track: Track,
    *,
    ppq: int | None = None,
    swing_percent: int | None = None,
    expand_roles: bool = True,
    apply_humanize: bool = True,
) -> list[Note]:
    """Flatten a track into absolute notes (ticks), with swing + humanize."""

    ppq = int(ppq if ppq is not None else project.ppq)
    swing_percent = int(swing_percent if swing_percent is not None else project.swing_percent)

    abs_notes: list[Note] = []

    if track.clips and track.patterns:
        for clip in track.clips:
            pat_name = resolve_pattern_name(
                base_pattern=clip.pattern,
                track_index=track_index,
                tick=clip.start,
                sections=list(getattr(project, "sections", []) or []),
                variations=list(getattr(project, "variations", []) or []),
            )
            pat = track.patterns.get(pat_name)
            if not pat:
                continue
            for rep in range(clip.repeats):
                base = clip.start + rep * pat.length
                for n in pat.notes:
                    start = apply_swing_tick(base + n.start, ppq, swing_percent)
                    abs_notes.append(
                        Note(
                            start=start,
                            duration=n.duration,
                            pitch=n.pitch,
                            velocity=n.velocity,
                            role=getattr(n, "role", None),
                            chance=getattr(n, "chance", 1.0),
                            mute=getattr(n, "mute", False),
                            accent=getattr(n, "accent", 1.0),
                            glide_ticks=getattr(n, "glide_ticks", 0),
                        )
                    )
    else:
        for n in track.notes:
            start = apply_swing_tick(n.start, ppq, swing_percent)
            abs_notes.append(
                Note(
                    start=start,
                    duration=n.duration,
                    pitch=n.pitch,
                    velocity=n.velocity,
                    role=getattr(n, "role", None),
                    chance=getattr(n, "chance", 1.0),
                    mute=getattr(n, "mute", False),
                    accent=getattr(n, "accent", 1.0),
                    glide_ticks=getattr(n, "glide_ticks", 0),
                )
            )

    if expand_roles:
        abs_notes = expand_role_notes(abs_notes, track=track)

    if apply_humanize:
        hs = HumanizeSettings(
            timing_ticks=int(getattr(track, "humanize_timing", 0) or 0),
            velocity=int(getattr(track, "humanize_velocity", 0) or 0),
            seed=int(getattr(track, "humanize_seed", 0) or 0),
        )
        abs_notes = humanize_notes(abs_notes, settings=hs)

    return abs_notes


def note_seed_base(track: Track, track_index: int, *, extra_seed: int = 0) -> int:
    return (int(getattr(track, "humanize_seed", 0) or 0) * 1000003) + (track_index * 9176) + int(extra_seed or 0)


def apply_note_chance(notes: list[Note], *, seed_base: int) -> list[Note]:
    out: list[Note] = []
    for n in notes:
        if getattr(n, "mute", False):
            continue
        chance = float(getattr(n, "chance", 1.0) or 1.0)
        if chance < 1.0:
            r = (seed_base + int(n.start) * 31 + int(n.pitch) * 131) & 0x7FFFFFFF
            if Random(r).random() > chance:
                continue
        out.append(n)
    return out
