from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from claw_daw.audio.sanity import MixSanity
from claw_daw.stylepacks.run import run_stylepack
from claw_daw.stylepacks.types import BeatSpec


class _DummyRunner:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def run_lines(self, *args, **kwargs) -> None:
        return None

    def require_project(self):
        return object()


def test_stylepack_raises_when_threshold_not_met(monkeypatch, tmp_path: Path) -> None:
    tools_dir = tmp_path / "tools"
    out_dir = tmp_path / "out"
    tools_dir.mkdir()
    out_dir.mkdir()

    script_path = tools_dir / "x.txt"
    script_path.write_text("new_project x 120\nsave_project out/x.json\n", encoding="utf-8")
    (out_dir / "x.preview.mp3").write_bytes(b"preview")

    monkeypatch.setattr("claw_daw.stylepacks.run.normalize_beatspec", lambda s: s)
    monkeypatch.setattr("claw_daw.stylepacks.run.get_stylepack", lambda n: SimpleNamespace(name=str(n), pack="trap"))
    monkeypatch.setattr("claw_daw.stylepacks.run.get_pack_v1", lambda n: SimpleNamespace(name=str(n), accept=lambda p: None))
    monkeypatch.setattr("claw_daw.stylepacks.run.compile_to_script", lambda *args, **kwargs: script_path)
    monkeypatch.setattr("claw_daw.stylepacks.run.HeadlessRunner", _DummyRunner)
    monkeypatch.setattr(
        "claw_daw.stylepacks.run.spectral_balance_score",
        lambda _p: SimpleNamespace(score=0.10, reasons=["low"], report={}),
    )
    monkeypatch.setattr(
        "claw_daw.stylepacks.run.analyze_mix_sanity",
        lambda _p: MixSanity(score=0.20, reasons=["quiet"], metrics={}, bands={}),
    )

    spec = BeatSpec(
        name="x",
        stylepack="trap_2020s",  # type: ignore[arg-type]
        max_attempts=1,
        score_threshold=0.60,
    )

    with pytest.raises(RuntimeError):
        run_stylepack(
            spec,
            out_prefix="x",
            soundfont="/tmp/fake.sf2",
            base_dir=tmp_path,
            tools_dir=str(tools_dir),
            out_dir=str(out_dir),
        )
