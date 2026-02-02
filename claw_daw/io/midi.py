from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from random import Random

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    import mido

from claw_daw.arrange.variations import resolve_pattern_name
from claw_daw.model.types import Note, Project, Track
from claw_daw.util.groove import HumanizeSettings, humanize_notes
from claw_daw.util.drumkit import expand_role_notes


@dataclass
class MidiExportResult:
    path: str
    ticks_per_beat: int


def _apply_swing_tick(tick: int, ppq: int, swing_percent: int) -> int:
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


def _iter_track_events(
    project: Project, track_index: int, track: Track, *, ppq: int, swing_percent: int
) -> list[tuple[int, Any]]:
    import mido  # type: ignore

    events: list[tuple[int, Any]] = []

    # at time 0: program + basic mixer
    events.append((0, mido.Message("program_change", program=track.program, channel=track.channel)))
    events.append((0, mido.Message("control_change", control=7, value=track.volume, channel=track.channel)))
    events.append((0, mido.Message("control_change", control=10, value=track.pan, channel=track.channel)))
    events.append((0, mido.Message("control_change", control=91, value=track.reverb, channel=track.channel)))
    events.append((0, mido.Message("control_change", control=93, value=track.chorus, channel=track.channel)))

    # Flatten arrangement to absolute notes, apply swing, then (optionally) humanize.
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
                    start = _apply_swing_tick(base + n.start, ppq, swing_percent)
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
            start = _apply_swing_tick(n.start, ppq, swing_percent)
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

    # Expand role-based drum notes via the selected kit.
    abs_notes = expand_role_notes(abs_notes, track=track)

    hs = HumanizeSettings(
        timing_ticks=int(getattr(track, "humanize_timing", 0) or 0),
        velocity=int(getattr(track, "humanize_velocity", 0) or 0),
        seed=int(getattr(track, "humanize_seed", 0) or 0),
    )
    abs_notes = humanize_notes(abs_notes, settings=hs)

    # Deterministic per-note expressions (chance/mute/accent).
    seed_base = (int(getattr(track, "humanize_seed", 0) or 0) * 1000003) + (track_index * 9176)

    for n in abs_notes:
        if getattr(n, "mute", False):
            continue
        chance = float(getattr(n, "chance", 1.0) or 1.0)
        if chance < 1.0:
            # stable per-note RNG key
            r = (seed_base + int(n.start) * 31 + int(n.pitch) * 131) & 0x7FFFFFFF
            if Random(r).random() > chance:
                continue

        vel = n.effective_velocity() if hasattr(n, "effective_velocity") else n.velocity

        events.append(
            (
                n.start,
                mido.Message("note_on", note=n.pitch, velocity=vel, channel=track.channel),
            )
        )
        events.append((n.end, mido.Message("note_off", note=n.pitch, velocity=0, channel=track.channel)))

    # stable ordering: by time then note_off after note_on.
    events.sort(key=lambda x: (x[0], 1 if x[1].type == "note_off" else 0))
    return events


def _apply_mute_solo(project: Project) -> set[int]:
    soloed = {i for i, t in enumerate(project.tracks) if t.solo}
    if soloed:
        return soloed
    return {i for i, t in enumerate(project.tracks) if not t.mute}


def project_to_midifile(project: Project, *, allowed_tracks: set[int] | None = None) -> Any:
    import mido  # type: ignore

    mf = mido.MidiFile(ticks_per_beat=project.ppq)

    tempo_track = mido.MidiTrack()
    tempo_track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(project.tempo_bpm), time=0))
    tempo_track.append(mido.MetaMessage("track_name", name=project.name, time=0))
    mf.tracks.append(tempo_track)

    allowed = allowed_tracks if allowed_tracks is not None else _apply_mute_solo(project)

    for idx, track in enumerate(project.tracks):
        if idx not in allowed:
            continue
        mt = mido.MidiTrack()
        mt.append(mido.MetaMessage("track_name", name=track.name, time=0))

        events = _iter_track_events(project, idx, track, ppq=project.ppq, swing_percent=project.swing_percent)
        last_t = 0
        for t, msg in events:
            delta = t - last_t
            last_t = t
            msg.time = delta
            mt.append(msg)
        mf.tracks.append(mt)

    return mf


def export_midi(project: Project, path: str | Path, *, allowed_tracks: set[int] | None = None) -> MidiExportResult:
    out = Path(path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    mf = project_to_midifile(project, allowed_tracks=allowed_tracks)
    mf.save(out)
    return MidiExportResult(path=str(out), ticks_per_beat=mf.ticks_per_beat)
