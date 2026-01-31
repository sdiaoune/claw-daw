from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import mido

from claw_daw.model.types import Project, Track


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


def _iter_track_events(track: Track, *, ppq: int, swing_percent: int) -> list[tuple[int, mido.Message]]:
    events: list[tuple[int, mido.Message]] = []

    # at time 0: program + basic mixer
    events.append((0, mido.Message("program_change", program=track.program, channel=track.channel)))
    events.append((0, mido.Message("control_change", control=7, value=track.volume, channel=track.channel)))
    events.append((0, mido.Message("control_change", control=10, value=track.pan, channel=track.channel)))
    events.append((0, mido.Message("control_change", control=91, value=track.reverb, channel=track.channel)))
    events.append((0, mido.Message("control_change", control=93, value=track.chorus, channel=track.channel)))

    # Render arrangement if present, else fall back to legacy linear notes
    if track.clips and track.patterns:
        for clip in track.clips:
            pat = track.patterns.get(clip.pattern)
            if not pat:
                continue
            for rep in range(clip.repeats):
                base = clip.start + rep * pat.length
                for note in pat.notes:
                    start = _apply_swing_tick(base + note.start, ppq, swing_percent)
                    end = start + note.duration
                    events.append(
                        (
                            start,
                            mido.Message(
                                "note_on",
                                note=note.pitch,
                                velocity=note.velocity,
                                channel=track.channel,
                            ),
                        )
                    )
                    events.append(
                        (
                            end,
                            mido.Message(
                                "note_off",
                                note=note.pitch,
                                velocity=0,
                                channel=track.channel,
                            ),
                        )
                    )
    else:
        for note in track.notes:
            start = _apply_swing_tick(note.start, ppq, swing_percent)
            end = start + note.duration
            events.append(
                (start, mido.Message("note_on", note=note.pitch, velocity=note.velocity, channel=track.channel))
            )
            events.append(
                (end, mido.Message("note_off", note=note.pitch, velocity=0, channel=track.channel))
            )

    # stable ordering: by time then note_off after note_on.
    events.sort(key=lambda x: (x[0], 1 if x[1].type == "note_off" else 0))
    return events


def _apply_mute_solo(project: Project) -> set[int]:
    soloed = {i for i, t in enumerate(project.tracks) if t.solo}
    if soloed:
        return soloed
    return {i for i, t in enumerate(project.tracks) if not t.mute}


def project_to_midifile(project: Project, *, allowed_tracks: set[int] | None = None) -> mido.MidiFile:
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

        events = _iter_track_events(track, ppq=project.ppq, swing_percent=project.swing_percent)
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
