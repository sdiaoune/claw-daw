from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from claw_daw.audio.sanity import MixSanity
from claw_daw.cli.headless import HeadlessRunner
from claw_daw.prompt.similarity import project_similarity
from claw_daw.stylepacks.compile import compile_to_script
from claw_daw.stylepacks.run import run_stylepack
from claw_daw.stylepacks.types import BeatSpec


def _project_from_script_path(path: Path):
    r = HeadlessRunner(soundfont=None, strict=True, dry_run=True)
    r.run_lines(path.read_text(encoding="utf-8").splitlines(), base_dir=path.parent)
    return r.require_project()


class _DummyRunner:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def run_lines(self, *args, **kwargs) -> None:
        return None

    def require_project(self):
        return object()


def test_compile_to_script_uses_single_base_generation_attempt(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_generate_from_genre_pack(*args, **kwargs):
        calls.append(dict(kwargs))
        script_path = tmp_path / "base.txt"
        script_path.write_text("new_project demo 124\nadd_track Drums 0\nnew_pattern 0 d 2:0\n", encoding="utf-8")
        return SimpleNamespace(script_path=script_path)

    monkeypatch.setattr("claw_daw.stylepacks.compile.generate_from_genre_pack", fake_generate_from_genre_pack)

    spec = BeatSpec(name="demo", stylepack="house", seed=9, max_attempts=6, length_bars=32, bpm=124, swing_percent=0)  # type: ignore[arg-type]
    compile_to_script(spec, out_prefix="demo", tools_dir=str(tmp_path))

    assert calls == [
        {
            "out_prefix": "demo",
            "tools_dir": str(tmp_path),
            "seed": 9,
            "max_attempts": 1,
            "max_similarity": None,
            "write_script": True,
        }
    ]


def test_compile_to_script_respects_explicit_seed(tmp_path: Path) -> None:
    spec = BeatSpec(
        name="demo",
        stylepack="trap_2020s",  # type: ignore[arg-type]
        seed=7,
        max_attempts=6,
        length_bars=32,
        bpm=140,
        swing_percent=0,
    )

    p1 = _project_from_script_path(compile_to_script(spec, out_prefix="a", tools_dir=str(tmp_path / "a")))
    p2 = _project_from_script_path(compile_to_script(spec, out_prefix="b", tools_dir=str(tmp_path / "b")))
    p3 = _project_from_script_path(compile_to_script(replace(spec, seed=8), out_prefix="c", tools_dir=str(tmp_path / "c")))

    assert project_similarity(p1, p2) == 1.0
    assert project_similarity(p1, p3) < 1.0


def test_run_stylepack_records_attempt_seeds_and_replays_chosen_attempt(monkeypatch, tmp_path: Path) -> None:
    tools_dir = tmp_path / "tools"
    out_dir = tmp_path / "out"
    tools_dir.mkdir()
    out_dir.mkdir()
    (out_dir / "seeded.preview.mp3").write_bytes(b"preview")

    compile_calls: list[tuple[int, dict[str, object]]] = []

    def fake_compile_to_script(spec: BeatSpec, *, out_prefix: str, tools_dir: str = "tools") -> Path:
        compile_calls.append((int(spec.seed), dict(spec.knobs)))
        script_path = Path(tools_dir) / f"{out_prefix}_{len(compile_calls)}.txt"
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text("new_project seeded 140\nsave_project out/seeded.json\n", encoding="utf-8")
        return script_path

    spectral_scores = iter([0.10, 0.75])

    monkeypatch.setattr("claw_daw.stylepacks.run.normalize_beatspec", lambda s: s)
    monkeypatch.setattr("claw_daw.stylepacks.run.get_stylepack", lambda n: SimpleNamespace(name=str(n), pack="trap"))
    monkeypatch.setattr("claw_daw.stylepacks.run.get_pack_v1", lambda n: SimpleNamespace(name=str(n), accept=lambda p: None))
    monkeypatch.setattr("claw_daw.stylepacks.run.compile_to_script", fake_compile_to_script)
    monkeypatch.setattr("claw_daw.stylepacks.run.HeadlessRunner", _DummyRunner)
    monkeypatch.setattr("claw_daw.stylepacks.run.project_similarity", lambda a, b: 0.0)
    monkeypatch.setattr(
        "claw_daw.stylepacks.run.spectral_balance_score",
        lambda _p: SimpleNamespace(score=next(spectral_scores), reasons=["ok"], report={}),
    )
    monkeypatch.setattr(
        "claw_daw.stylepacks.run.analyze_mix_sanity",
        lambda _p: MixSanity(score=0.80, reasons=["quiet"], metrics={}, bands={}),
    )
    monkeypatch.setattr(
        "claw_daw.stylepacks.run.run_quality_workflow",
        lambda **kwargs: {"ok": True, "project_json": kwargs["project_json"]},
    )

    spec = BeatSpec(
        name="seeded",
        stylepack="trap_2020s",  # type: ignore[arg-type]
        seed=10,
        max_attempts=3,
        length_bars=32,
        bpm=140,
        swing_percent=0,
        score_threshold=0.60,
    )

    report_path = run_stylepack(
        spec,
        out_prefix="seeded",
        soundfont="/tmp/fake.sf2",
        base_dir=tmp_path,
        tools_dir=str(tools_dir),
        out_dir=str(out_dir),
    )

    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    assert report["seed_used"] == 10
    assert [attempt["seed"] for attempt in report["attempts"]] == [10, 11]
    assert compile_calls[0][0] == 10
    assert compile_calls[1][0] == 11
    assert compile_calls[2][0] == 11
    assert compile_calls[1][1] == compile_calls[2][1]
    assert compile_calls[0][1] != compile_calls[1][1]
