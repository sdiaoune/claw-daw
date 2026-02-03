from __future__ import annotations

from pathlib import Path

from claw_daw.arrange.arrange_spec import load_arrange_spec
from claw_daw.arrange.compiler import compile_arrangement
from claw_daw.arrange.types import Pattern
from claw_daw.model.types import Note, Project, Track


def _mk_pat(name: str, length: int, pitch: int) -> Pattern:
    return Pattern(name=name, length=length, notes=[Note(start=0, duration=length // 4, pitch=pitch, velocity=100)])


def test_arrange_spec_compiler_places_sections_and_applies_cues(tmp_path: Path) -> None:
    p = Project(name="t", ppq=480)
    tpb = p.ppq * 4

    drums = Track(name="Drums", channel=9)
    drums.patterns["main"] = _mk_pat("main", tpb, 36)
    drums.patterns["fill"] = _mk_pat("fill", tpb, 38)

    bass = Track(name="Bass", channel=1)
    bass.patterns["main"] = _mk_pat("main", tpb, 36)

    p.tracks = [drums, bass]

    spec_path = tmp_path / "arr.yaml"
    spec_path.write_text(
        """
version: 1
base_patterns:
  0: main
  1: main
sections:
  - name: intro
    bars: 4
    cues:
      - type: dropout
        at: end
        bars: 1
        tracks: [1]
  - name: chorus
    bars: 4
    cues:
      - type: fill
        at: end
        bars: 1
        tracks: [0]
        pattern: fill
""".lstrip(),
        encoding="utf-8",
    )

    spec = load_arrange_spec(spec_path)
    compile_arrangement(p, spec)

    assert [s.name for s in p.sections] == ["intro", "chorus"]
    assert p.sections[0].start == 0
    assert p.sections[0].length == 4 * tpb
    assert p.sections[1].start == 4 * tpb
    assert p.sections[1].length == 4 * tpb

    # Drums: 8 clips total, last bar is fill.
    d_starts = sorted(c.start for c in p.tracks[0].clips)
    assert d_starts == [i * tpb for i in range(8)]
    d_last = [c for c in p.tracks[0].clips if c.start == 7 * tpb][0]
    assert d_last.pattern == "fill"

    # Bass: dropout at end of intro => remove bar 3.
    b_starts = sorted(c.start for c in p.tracks[1].clips)
    assert 3 * tpb not in b_starts
    assert b_starts == [i * tpb for i in range(8) if i != 3]
