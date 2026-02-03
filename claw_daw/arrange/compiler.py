from __future__ import annotations

from dataclasses import replace

from claw_daw.arrange.arrange_spec import ArrangeSpec, CueSpec
from claw_daw.arrange.sections import Section
from claw_daw.arrange.types import Clip
from claw_daw.model.types import Project, Track


def ticks_per_bar(proj: Project) -> int:
    return int(proj.ppq) * 4


def _choose_default_pattern_name(track: Track) -> str:
    if not track.patterns:
        raise ValueError(f"track '{track.name}' has no patterns")

    # common conventions
    for preferred in ("main", "a", "A", "p1", "P1"):
        if preferred in track.patterns:
            return preferred

    # stable deterministic choice
    return sorted(track.patterns.keys())[0]


def _clear_all_clips(proj: Project) -> None:
    for t in proj.tracks:
        t.clips = []


def _place_track_loop(
    *,
    proj: Project,
    track_index: int,
    pattern_name: str,
    song_ticks: int,
) -> None:
    t = proj.tracks[track_index]
    if pattern_name not in t.patterns:
        raise KeyError(f"track {track_index} missing pattern: {pattern_name}")

    pat = t.patterns[pattern_name]
    if pat.length <= 0:
        raise ValueError("pattern length must be > 0")

    if song_ticks % pat.length != 0:
        raise ValueError(
            f"song length ({song_ticks} ticks) is not a multiple of pattern '{pattern_name}' length ({pat.length})"
        )

    steps = song_ticks // pat.length
    t.clips = [Clip(pattern=pattern_name, start=i * pat.length, repeats=1) for i in range(steps)]


def _apply_dropout(
    *,
    proj: Project,
    track_index: int,
    start_tick: int,
    end_tick: int,
) -> None:
    t = proj.tracks[track_index]
    t.clips = [c for c in t.clips if not (start_tick <= c.start < end_tick)]


def _apply_fill(
    *,
    proj: Project,
    track_index: int,
    fill_pattern: str,
    start_tick: int,
    end_tick: int,
) -> None:
    t = proj.tracks[track_index]
    if fill_pattern not in t.patterns:
        raise KeyError(f"track {track_index} missing fill pattern: {fill_pattern}")

    new_clips: list[Clip] = []
    for c in t.clips:
        if start_tick <= c.start < end_tick:
            new_clips.append(replace(c, pattern=fill_pattern))
        else:
            new_clips.append(c)
    t.clips = new_clips


def _cue_window(*, proj: Project, sec_start: int, sec_len: int, cue: CueSpec) -> tuple[int, int]:
    tpb = ticks_per_bar(proj)
    win = cue.bars * tpb
    if win > sec_len:
        raise ValueError(f"cue window ({win} ticks) exceeds section length ({sec_len} ticks)")

    if cue.at == "start":
        return sec_start, sec_start + win
    return sec_start + sec_len - win, sec_start + sec_len


def compile_arrangement(
    proj: Project,
    spec: ArrangeSpec,
    *,
    clear_existing: bool = True,
) -> Project:
    """Apply an ArrangeSpec to a Project.

    This is deterministic and does not use randomness.

    It will:
    - set proj.sections based on section bar counts
    - place clips across the full song using base patterns (per track)
    - apply cues (dropouts/fills) at section boundaries

    Returns the same Project instance (mutated) for convenience.
    """

    tpb = ticks_per_bar(proj)

    # Build sections with absolute tick ranges.
    cur = 0
    sections: list[Section] = []
    for s in spec.sections:
        length = s.bars * tpb
        sections.append(Section(name=s.name, start=cur, length=length))
        cur += length

    song_ticks = cur

    if clear_existing:
        _clear_all_clips(proj)

    # Base loop placement per track.
    for ti, tr in enumerate(proj.tracks):
        base = spec.base_patterns.get(ti) or _choose_default_pattern_name(tr)
        _place_track_loop(proj=proj, track_index=ti, pattern_name=base, song_ticks=song_ticks)

    # Apply cues.
    for sec_spec, sec in zip(spec.sections, sections, strict=True):
        for cue in sec_spec.cues:
            w0, w1 = _cue_window(proj=proj, sec_start=sec.start, sec_len=sec.length, cue=cue)
            for ti in cue.tracks:
                if ti < 0 or ti >= len(proj.tracks):
                    raise IndexError(f"cue track index out of range: {ti}")
                if cue.type == "dropout":
                    _apply_dropout(proj=proj, track_index=ti, start_tick=w0, end_tick=w1)
                elif cue.type == "fill":
                    assert cue.pattern is not None
                    _apply_fill(
                        proj=proj,
                        track_index=ti,
                        fill_pattern=cue.pattern,
                        start_tick=w0,
                        end_tick=w1,
                    )
                else:
                    raise ValueError(f"unknown cue type: {cue.type}")

    proj.sections = sections
    proj.dirty = True
    return proj
