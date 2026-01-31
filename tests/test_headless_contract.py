from __future__ import annotations

import json
from pathlib import Path

from claw_daw.cli.headless import HeadlessRunner


def test_headless_include_and_dump_state(tmp_path: Path) -> None:
    inc = tmp_path / "inc.txt"
    inc.write_text(
        "new_project test 120\n"
        "add_track Drums 0\n"
        "new_pattern 0 d 1920\n"
        "place_pattern 0 d 0 4\n",
        encoding="utf-8",
    )

    script = [f"include {inc}\n", f"dump_state {tmp_path/'state.json'}\n"]

    r = HeadlessRunner(soundfont=None, strict=True, dry_run=True)
    r.run_lines([s.strip() for s in script], base_dir=tmp_path)

    # dry_run should still allow dump_state (no audio)
    state_path = tmp_path / "state.json"
    assert state_path.exists()

    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload["name"] == "test"
    assert payload["derived"]["song_length_ticks"] >= 0
    assert payload["derived"]["song_length_seconds"] >= 0
