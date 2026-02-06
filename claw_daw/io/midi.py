from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claw_daw.model.types import Project, Track
from claw_daw.util.notes import apply_note_chance, flatten_track_notes, note_seed_base


@dataclass
class MidiExportResult:
    path: str
    ticks_per_beat: int


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

    abs_notes = flatten_track_notes(project, track_index, track, ppq=ppq, swing_percent=swing_percent)
    abs_notes = apply_note_chance(abs_notes, seed_base=note_seed_base(track, track_index))

    for n in abs_notes:
        vel = n.effective_velocity() if hasattr(n, "effective_velocity") else n.velocity
        events.append((n.start, mido.Message("note_on", note=n.pitch, velocity=vel, channel=track.channel)))
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
