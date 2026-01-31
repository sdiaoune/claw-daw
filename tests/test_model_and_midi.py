from __future__ import annotations

import json
from pathlib import Path

from claw_daw.io.midi import project_to_midifile
from claw_daw.io.project_json import load_project, save_project
from claw_daw.model.types import Note, Project, Track


def test_project_json_round_trip(tmp_path: Path) -> None:
    p = Project(name="Test", tempo_bpm=120)
    p.tracks.append(Track(name="Piano", channel=0, program=0))
    p.tracks[0].notes.append(Note(start=0, duration=480, pitch=60, velocity=100))

    out = tmp_path / "proj.json"
    save_project(p, out)

    loaded = load_project(out)
    assert loaded.name == "Test"
    assert loaded.tempo_bpm == 120
    assert len(loaded.tracks) == 1
    assert loaded.tracks[0].name == "Piano"
    assert loaded.tracks[0].notes[0].pitch == 60


def test_midi_export_contains_program_and_notes(tmp_path: Path) -> None:
    p = Project(name="Test", tempo_bpm=120)
    t = Track(name="Piano", channel=0, program=10, volume=101, pan=32)
    t.notes.append(Note(start=0, duration=240, pitch=64, velocity=90))
    p.tracks.append(t)

    mf = project_to_midifile(p)
    # tempo track + 1 musical track
    assert len(mf.tracks) == 2

    msgs = list(mf.tracks[1])
    assert any(getattr(m, "type", None) == "program_change" and m.program == 10 for m in msgs)
    assert any(getattr(m, "type", None) == "control_change" and m.control == 7 and m.value == 101 for m in msgs)
    assert any(getattr(m, "type", None) == "control_change" and m.control == 10 and m.value == 32 for m in msgs)
    assert any(getattr(m, "type", None) == "note_on" and m.note == 64 for m in msgs)
    assert any(getattr(m, "type", None) == "note_off" and m.note == 64 for m in msgs)


def test_mute_solo_affects_export() -> None:
    p = Project(name="Test")
    t1 = Track(name="T1", channel=0, program=0, mute=True)
    t2 = Track(name="T2", channel=1, program=0, mute=False)
    p.tracks = [t1, t2]

    mf = project_to_midifile(p)
    # tempo + only t2
    assert len(mf.tracks) == 2
    assert any(m.type == "track_name" and m.name == "T2" for m in mf.tracks[1])

    t1.solo = True
    mf2 = project_to_midifile(p)
    # tempo + only soloed t1
    assert len(mf2.tracks) == 2
    assert any(m.type == "track_name" and m.name == "T1" for m in mf2.tracks[1])
