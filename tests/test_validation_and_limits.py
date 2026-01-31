from __future__ import annotations

import json
from pathlib import Path

from claw_daw.io.project_json import load_project, save_project
from claw_daw.model.types import Project, Track
from claw_daw.util.limits import MAX_TRACKS


def test_schema_migration_adds_render_region_fields(tmp_path: Path) -> None:
    # Simulate a v1 project dict (no schema_version, no render region fields)
    payload = {
        "name": "Old",
        "tempo_bpm": 123,
        "ppq": 480,
        "tracks": [],
    }
    pth = tmp_path / "old.json"
    pth.write_text(json.dumps(payload), encoding="utf-8")

    p = load_project(pth)
    assert p.name == "Old"
    assert hasattr(p, "render_start")
    assert hasattr(p, "render_end")


def test_limits_truncate_tracks_on_load(tmp_path: Path) -> None:
    p = Project(name="Many")
    for i in range(MAX_TRACKS + 5):
        p.tracks.append(Track(name=f"T{i}", channel=i % 16))

    out = tmp_path / "many.json"
    save_project(p, out)

    loaded = load_project(out)
    assert len(loaded.tracks) == MAX_TRACKS
