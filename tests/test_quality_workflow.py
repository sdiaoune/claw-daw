from __future__ import annotations

import json
from pathlib import Path

from claw_daw.io.project_json import save_project
from claw_daw.model.types import Project, Track
from claw_daw.quality_workflow import prepare_mix_spec, validate_mix_spec


def _make_project() -> Project:
    p = Project(name="q", tempo_bpm=140)
    p.tracks = [
        Track(name="Drums", channel=9, program=0),
        Track(name="Bass", channel=0, program=38),
        Track(name="Lead", channel=1, program=81),
    ]
    return p


def _write_presets(path: Path) -> None:
    payload = {
        "edm_streaming": {
            "mix": {
                "roles": {
                    "drums": {"sends": {"reverb": 0.0, "delay": 0.0}},
                    "bass": {"sends": {"reverb": 0.0, "delay": 0.0}},
                    "music": {"highpass_hz": 150},
                },
                "busses": {
                    "bass": {"mono_below_hz": 130},
                    "music": {"comp": {"threshold_db": -30, "ratio": 1.6, "attack_ms": 25, "release_ms": 160}},
                },
                "master": {"mono_below_hz": 130},
                "sidechain": {"targets": ["bass"], "params": {"threshold_db": -24, "ratio": 6, "attack_ms": 5, "release_ms": 120}},
            }
        }
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_prepare_mix_spec_assigns_bus_and_sidechain(tmp_path: Path) -> None:
    proj_path = tmp_path / "proj.json"
    mix_path = tmp_path / "mix.json"
    presets_path = tmp_path / "presets.json"

    save_project(_make_project(), str(proj_path))
    _write_presets(presets_path)

    prepare_mix_spec(
        str(proj_path),
        preset="edm_streaming",
        presets_path=str(presets_path),
        mix_out=str(mix_path),
    )

    ok, checks = validate_mix_spec(str(proj_path), str(mix_path))
    assert ok is True
    assert any("sidechain kick->bass present" in c for c in checks)


def test_validate_mix_spec_fails_for_missing_sidechain(tmp_path: Path) -> None:
    proj_path = tmp_path / "proj.json"
    save_project(_make_project(), str(proj_path))

    bad_mix = {
        "tracks": {"0": {}, "1": {}, "2": {}},
        "busses": {"bass": {"mono_below_hz": 130}, "music": {"comp": {"threshold_db": -20}}},
        "master": {"mono_below_hz": 130},
        "sidechain": [],
    }
    mix_path = tmp_path / "bad.mix.json"
    mix_path.write_text(json.dumps(bad_mix), encoding="utf-8")

    ok, checks = validate_mix_spec(str(proj_path), str(mix_path))
    assert ok is False
    assert any("sidechain kick->bass missing" in c for c in checks)
