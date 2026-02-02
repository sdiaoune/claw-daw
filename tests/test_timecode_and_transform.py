from __future__ import annotations

from claw_daw.arrange.types import Pattern
from claw_daw.arrange.transform import reverse, shift, stretch, transpose
from claw_daw.model.types import Note, Project
from claw_daw.util.timecode import parse_timecode_ticks


def test_bar_beat_timecode_parses() -> None:
    p = Project(name="x", ppq=480)
    assert parse_timecode_ticks(p, "0:0") == 0
    assert parse_timecode_ticks(p, "1:0") == 480 * 4
    assert parse_timecode_ticks(p, "0:2") == 480 * 2
    assert parse_timecode_ticks(p, "2:1:120") == 2 * 480 * 4 + 1 * 480 + 120


def test_pattern_transform_primitives() -> None:
    pat = Pattern(name="p", length=480 * 4)
    pat.notes = [Note(start=0, duration=120, pitch=60, velocity=100), Note(start=240, duration=120, pitch=64, velocity=80)]

    t = transpose(pat, 12)
    assert [n.pitch for n in t.notes] == [72, 76]

    s = shift(pat, 120)
    assert [n.start for n in s.notes] == [120, 360]

    st = stretch(pat, 2.0)
    assert st.length == pat.length * 2
    assert st.notes[0].start == 0
    assert st.notes[1].start == 480

    r = reverse(pat)
    # note at start becomes near end
    assert r.notes[0].start >= 0
