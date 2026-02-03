from __future__ import annotations

import json
from pathlib import Path

from claw_daw.cli.headless import HeadlessRunner


def _run(script_lines: list[str], *, tmp_path: Path) -> dict:
    r = HeadlessRunner(soundfont=None, strict=True, dry_run=True)
    r.run_lines([ln.strip() for ln in script_lines if ln.strip()], base_dir=tmp_path)
    state = tmp_path / "state.json"
    assert state.exists()
    return json.loads(state.read_text(encoding="utf-8"))


def test_gen_drum_macros_creates_expected_patterns(tmp_path: Path) -> None:
    script = [
        "new_project t 120",
        "add_track Drums 0",
        "new_pattern 0 d 1920",
        # minimal base groove
        "add_note_pat 0 d 36 0 120 115",  # kick
        "add_note_pat 0 d 38 480 120 108",  # snare (beat 2)
        "add_note_pat 0 d 38 1440 120 108",  # snare (beat 4)
        "add_note_pat 0 d 42 0 60 62",  # hat
        "add_note_pat 0 d 42 240 60 62",
        "add_note_pat 0 d 42 480 60 62",
        "add_note_pat 0 d 42 720 60 62",
        "gen_drum_macros 0 d out_prefix=dr seed=123 make=both",
        f"dump_state {tmp_path/'state.json'}",
    ]

    payload = _run(script, tmp_path=tmp_path)
    pats = payload["tracks"][0]["patterns"]

    assert "dr_fill_hatroll" in pats
    assert "dr_fill_kickturn" in pats
    assert "dr_v4" in pats
    assert "dr_v8" in pats

    assert pats["dr_fill_hatroll"]["length"] == 1920
    assert pats["dr_fill_kickturn"]["length"] == 1920
    assert pats["dr_v4"]["length"] == 1920 * 4
    assert pats["dr_v8"]["length"] == 1920 * 8

    # basic sanity: fills should contain notes near the end of the bar
    fill_hat_starts = [n["start"] for n in pats["dr_fill_hatroll"]["notes"]]
    assert any(s >= 1600 for s in fill_hat_starts)


def test_gen_drum_macros_is_deterministic(tmp_path: Path) -> None:
    base = [
        "new_project t 120",
        "add_track Drums 0",
        "new_pattern 0 d 1920",
        "add_note_pat 0 d 36 0 120 115",
        "add_note_pat 0 d 38 480 120 108",
        "add_note_pat 0 d 38 1440 120 108",
        "add_note_pat 0 d 42 0 60 62",
        "add_note_pat 0 d 42 240 60 62",
        "add_note_pat 0 d 42 480 60 62",
        "add_note_pat 0 d 42 720 60 62",
        "gen_drum_macros 0 d out_prefix=dr seed=999 make=both",
    ]

    p1 = _run([*base, f"dump_state {tmp_path/'state.json'}"], tmp_path=tmp_path)

    tmp_path2 = tmp_path / "r2"
    tmp_path2.mkdir()
    p2 = _run([*base, f"dump_state {tmp_path2/'state.json'}"], tmp_path=tmp_path2)

    assert p1["tracks"][0]["patterns"]["dr_v4"] == p2["tracks"][0]["patterns"]["dr_v4"]
    assert p1["tracks"][0]["patterns"]["dr_v8"] == p2["tracks"][0]["patterns"]["dr_v8"]
