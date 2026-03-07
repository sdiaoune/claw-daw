from __future__ import annotations

from pathlib import Path

import pytest

import claw_daw.__main__ as cli_main
import claw_daw.cli.headless as headless_mod
import claw_daw.io.fl_studio as fl_studio
from claw_daw.arrange.types import Clip, Pattern
from claw_daw.cli.headless import HeadlessRunner
from claw_daw.io.project_json import save_project
from claw_daw.model.types import Note, Project, Track


def _make_project(track_count: int = 2) -> Project:
    p = Project(name="FL Export", tempo_bpm=128)
    names = ["Drums", "Bass", "Lead", "Pad", "FX", "Perc", "Synth", "Keys"]
    for idx in range(track_count):
        t = Track(name=names[idx % len(names)], channel=idx % 16, program=idx % 128)
        t.notes.append(Note(start=0, duration=480, pitch=60 + (idx % 12), velocity=100))
        p.tracks.append(t)
    return p


def test_build_flp_export_model_assigns_expected_layout(tmp_path: Path) -> None:
    model = fl_studio.build_flp_export_model(_make_project(2), tmp_path / "handoff")

    assert Path(model.out_flp).name == "handoff.flp"
    assert Path(model.assets_dir).name == "handoff.flp.assets"
    assert Path(model.master_ref_path).name == "master_ref.wav"
    assert Path(model.import_midi_path).name == ".project_import.mid"
    assert [Path(track.stem_path).name for track in model.tracks] == [
        "track_00_drums.wav",
        "track_01_bass.wav",
    ]
    assert [(track.midi_lane, track.audio_lane) for track in model.tracks] == [(1, 2), (3, 4)]


def test_build_flp_export_model_enforces_track_and_clip_caps() -> None:
    with pytest.raises(ValueError, match="supports up to 16 tracks"):
        fl_studio.build_flp_export_model(_make_project(17), "out/too_many")

    p = Project(name="Clip Heavy", tempo_bpm=120)
    t = Track(name="Lead", channel=0, program=80)
    pat = Pattern(name="p1", length=480)
    pat.notes.append(Note(start=0, duration=120, pitch=60, velocity=100))
    t.patterns["p1"] = pat
    t.clips.append(Clip(pattern="p1", start=0, repeats=257))
    p.tracks.append(t)

    with pytest.raises(ValueError, match="supports up to 256 expanded clip placements"):
        fl_studio.build_flp_export_model(p, "out/too_many_clips")


def test_export_fl_studio_project_writes_assets_and_returns_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    proj = _make_project(2)
    mix_path = tmp_path / "mix.json"
    mix_path.write_text('{"tracks":{"0":{"gain_db":-1.0}}}', encoding="utf-8")
    calls: dict[str, object] = {}

    def fake_render_stems(project: Project, model: fl_studio.FlpExportModel, *, soundfont: str, mix: dict | None) -> None:
        calls["stems_soundfont"] = soundfont
        calls["stems_mix"] = mix
        for track in model.tracks:
            path = Path(track.stem_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"stem")

    def fake_render_master(
        project: Project,
        model: fl_studio.FlpExportModel,
        *,
        soundfont: str,
        mix: dict | None,
        preset: str,
    ) -> None:
        calls["master_soundfont"] = soundfont
        calls["master_preset"] = preset
        Path(model.master_ref_path).write_bytes(b"master")

    def fake_write_import_midi(project: Project, model: fl_studio.FlpExportModel) -> None:
        Path(model.import_midi_path).parent.mkdir(parents=True, exist_ok=True)
        Path(model.import_midi_path).write_bytes(b"midi")

    def fake_save(model: fl_studio.FlpExportModel, *, app_path: str | None) -> None:
        calls["app_path"] = app_path
        Path(model.out_flp).parent.mkdir(parents=True, exist_ok=True)
        Path(model.out_flp).write_bytes(b"FLhd")

    monkeypatch.setattr(fl_studio, "_render_track_stems", fake_render_stems)
    monkeypatch.setattr(fl_studio, "_render_master_reference", fake_render_master)
    monkeypatch.setattr(fl_studio, "_write_import_midi", fake_write_import_midi)
    monkeypatch.setattr(fl_studio, "_save_project_with_fl_studio", fake_save)

    result = fl_studio.export_fl_studio_project(
        proj,
        out_path=tmp_path / "transfer",
        soundfont="dummy.sf2",
        mix_path=str(mix_path),
        preset="punchy",
        app_path="/Applications/FL Studio 2024.app",
    )

    assert Path(result.flp_path).exists()
    assert Path(result.master_ref_path).exists()
    assert all(Path(path).exists() for path in result.stem_paths)
    assert calls["stems_soundfont"] == "dummy.sf2"
    assert calls["master_preset"] == "punchy"
    assert calls["app_path"] == "/Applications/FL Studio 2024.app"
    assert calls["stems_mix"] == {"tracks": {"0": {"gain_db": -1.0}}}


def test_headless_export_flp_command_dispatches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_export(
        project: Project,
        *,
        out_path: str | Path,
        soundfont: str,
        mix_path: str | None = None,
        preset: str = "clean",
        quality_preset: str = "edm_streaming",
        app_path: str | None = None,
    ) -> fl_studio.FlpExportResult:
        captured["project"] = project
        captured["out_path"] = str(out_path)
        captured["soundfont"] = soundfont
        captured["mix_path"] = mix_path
        captured["preset"] = preset
        captured["quality_preset"] = quality_preset
        return fl_studio.FlpExportResult(
            flp_path=str(tmp_path / "song.flp"),
            assets_dir=str(tmp_path / "song.flp.assets"),
            master_ref_path=str(tmp_path / "song.flp.assets" / "master_ref.wav"),
            stem_paths=(),
        )

    monkeypatch.setattr(headless_mod, "export_fl_studio_project", fake_export)

    runner = HeadlessRunner(soundfont="dummy.sf2", strict=True, dry_run=False)
    runner.run_lines(
        [
            "new_project export_me 128",
            "add_track Lead 80",
            "insert_note 0 60 0 480 100",
            "export_flp out/handoff mix=tools/handoff.mix.json preset=punchy quality_preset=edm_club",
        ],
        base_dir=tmp_path,
    )

    assert isinstance(captured["project"], Project)
    assert captured["soundfont"] == "dummy.sf2"
    assert captured["out_path"] == "out/handoff"
    assert captured["mix_path"] == "tools/handoff.mix.json"
    assert captured["preset"] == "punchy"
    assert captured["quality_preset"] == "edm_club"


def test_cli_flp_json_input_uses_project_exporter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    proj_path = tmp_path / "song.json"
    save_project(_make_project(2), proj_path)
    captured: dict[str, object] = {}

    def fake_export(project: Project, **kwargs: object) -> fl_studio.FlpExportResult:
        captured["project"] = project
        captured.update(kwargs)
        return fl_studio.FlpExportResult(
            flp_path=str(tmp_path / "song.flp"),
            assets_dir=str(tmp_path / "song.flp.assets"),
            master_ref_path=str(tmp_path / "song.flp.assets" / "master_ref.wav"),
            stem_paths=(),
        )

    monkeypatch.setattr(fl_studio, "export_fl_studio_project", fake_export)

    cli_main.main(
        [
            "flp",
            str(proj_path),
            "--out",
            str(tmp_path / "song"),
            "--soundfont",
            "dummy.sf2",
            "--mix",
            str(tmp_path / "mix.json"),
        ]
    )

    out = capsys.readouterr().out
    assert "flp:" in out
    assert isinstance(captured["project"], Project)
    assert captured["soundfont"] == "dummy.sf2"


def test_cli_flp_script_input_ignores_export_lines(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script = tmp_path / "song.txt"
    script.write_text(
        "new_project from_script 120\n"
        "add_track Lead 80\n"
        "insert_note 0 60 0 480 100\n"
        "save_project out/ignored.json\n"
        "export_mp3 out/ignored.mp3 preset=clean\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_export(project: Project, **kwargs: object) -> fl_studio.FlpExportResult:
        captured["project"] = project
        captured.update(kwargs)
        return fl_studio.FlpExportResult(
            flp_path=str(tmp_path / "song.flp"),
            assets_dir=str(tmp_path / "song.flp.assets"),
            master_ref_path=str(tmp_path / "song.flp.assets" / "master_ref.wav"),
            stem_paths=(),
        )

    monkeypatch.setattr(fl_studio, "export_fl_studio_project", fake_export)

    cli_main.main(
        [
            "flp",
            str(script),
            "--out",
            str(tmp_path / "handoff.flp"),
            "--soundfont",
            "dummy.sf2",
        ]
    )

    proj = captured["project"]
    assert isinstance(proj, Project)
    assert proj.name == "from_script"
    assert len(proj.tracks) == 1
