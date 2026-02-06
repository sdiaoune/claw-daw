from __future__ import annotations

import os
import wave
from pathlib import Path

from claw_daw.audio.sample_packs import load_sample_pack, scan_sample_pack
from claw_daw.io.project_json import load_project, save_project
from claw_daw.model.types import Project, SamplePackSpec, Track


def _write_wav(path: Path, *, sr: int = 44100, dur_s: float = 0.05) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = int(sr * dur_s)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for i in range(n):
            v = int(16000 * (1.0 if (i % 20) < 10 else -1.0))
            frames += int.to_bytes(v, 2, "little", signed=True)
        wf.writeframes(bytes(frames))


def test_scan_sample_pack_and_load(tmp_path: Path) -> None:
    prev = os.environ.get("CLAW_DAW_SAMPLE_PACKS_DIR")
    os.environ["CLAW_DAW_SAMPLE_PACKS_DIR"] = str(tmp_path / "packs")

    pack_dir = tmp_path / "pack"
    _write_wav(pack_dir / "Kick_01.wav")
    _write_wav(pack_dir / "Snare_01.wav")
    _write_wav(pack_dir / "Open_Hat.wav")

    try:
        pack = scan_sample_pack(pack_dir, pack_id="test_pack")
        assert pack.id == "test_pack"
        assert "kick" in pack.roles
        assert "snare" in pack.roles
        assert "hat_open" in pack.roles

        loaded = load_sample_pack("test_pack")
        assert loaded.root == str(pack_dir.resolve())
    finally:
        if prev is None:
            os.environ.pop("CLAW_DAW_SAMPLE_PACKS_DIR", None)
        else:
            os.environ["CLAW_DAW_SAMPLE_PACKS_DIR"] = prev


def test_sample_pack_round_trip_in_project_json(tmp_path: Path) -> None:
    p = Project(name="Test", tempo_bpm=120)
    t = Track(name="Drums", channel=9)
    t.sample_pack = SamplePackSpec(id="my_pack", seed=7, gain_db=-1.5)
    p.tracks.append(t)

    out = tmp_path / "proj.json"
    save_project(p, out)
    loaded = load_project(out)

    sp = loaded.tracks[0].sample_pack
    assert sp is not None
    assert sp.id == "my_pack"
    assert sp.seed == 7
    assert sp.gain_db == -1.5
