from __future__ import annotations

from claw_daw.arrange.sections import Section, Variation
from claw_daw.arrange.types import Clip, Pattern
from claw_daw.io.midi import project_to_midifile
from claw_daw.model.types import Note, Project, Track


def test_humanize_is_deterministic() -> None:
    p = Project(name="t")
    t = Track(name="P", channel=0)
    t.humanize_timing = 5
    t.humanize_velocity = 3
    t.humanize_seed = 123
    t.notes.append(Note(start=0, duration=120, pitch=60, velocity=90))
    p.tracks = [t]

    mf1 = project_to_midifile(p)
    mf2 = project_to_midifile(p)
    # deterministic: exact same delta-times
    assert [m.time for m in mf1.tracks[1] if hasattr(m, "time")] == [m.time for m in mf2.tracks[1] if hasattr(m, "time")]


def test_variation_swaps_pattern_in_section() -> None:
    p = Project(name="t")
    p.sections = [Section(name="A", start=0, length=p.ppq * 4)]
    p.variations = [Variation(section="A", track_index=0, src_pattern="p1", dst_pattern="p2")]

    tr = Track(name="T", channel=0)
    tr.patterns["p1"] = Pattern(name="p1", length=p.ppq * 4, notes=[Note(start=0, duration=120, pitch=60, velocity=90)])
    tr.patterns["p2"] = Pattern(name="p2", length=p.ppq * 4, notes=[Note(start=0, duration=120, pitch=62, velocity=90)])
    tr.clips = [Clip(pattern="p1", start=0, repeats=1)]
    p.tracks = [tr]

    mf = project_to_midifile(p)
    notes = [m.note for m in mf.tracks[1] if getattr(m, "type", None) == "note_on"]
    assert 62 in notes
    assert 60 not in notes
