from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claw_daw.audio.mastering import master_wav
from claw_daw.audio.render import render_project_wav
from claw_daw.audio.stems import export_stems
from claw_daw.io.midi import export_midi
from claw_daw.model.types import Project

MAX_FLP_TRACKS = 16
MAX_FLP_CLIPS = 256


@dataclass(frozen=True)
class FlpTrackAsset:
    track_index: int
    track_name: str
    stem_path: str
    midi_lane: int
    audio_lane: int


@dataclass(frozen=True)
class FlpExportModel:
    project_name: str
    tempo_bpm: int
    out_flp: str
    assets_dir: str
    master_ref_path: str
    import_midi_path: str
    expanded_clip_count: int
    tracks: tuple[FlpTrackAsset, ...]


@dataclass(frozen=True)
class FlpExportResult:
    flp_path: str
    assets_dir: str
    master_ref_path: str
    stem_paths: tuple[str, ...]


def _slugify(value: str) -> str:
    out: list[str] = []
    prev_us = False
    for ch in str(value or "").strip().lower():
        if ("a" <= ch <= "z") or ("0" <= ch <= "9"):
            out.append(ch)
            prev_us = False
            continue
        if not prev_us:
            out.append("_")
            prev_us = True
    slug = "".join(out).strip("_")
    return slug or "track"


def _normalize_flp_path(out_path: str | Path) -> Path:
    p = Path(out_path).expanduser()
    if p.suffix.lower() != ".flp":
        p = p.parent / f"{p.name}.flp"
    return p


def _expanded_clip_count(project: Project) -> int:
    total = 0
    for track in project.tracks:
        if track.clips and track.patterns:
            for clip in track.clips:
                total += max(1, int(getattr(clip, "repeats", 1) or 1))
        elif track.notes:
            total += 1
    return total


def _load_mix_spec(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    mp = Path(path).expanduser()
    raw = mp.read_text(encoding="utf-8")
    if mp.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except Exception as e:
            raise RuntimeError("mix=... requires PyYAML for .yaml/.yml") from e
        return yaml.safe_load(raw) or {}
    return json.loads(raw or "{}")


def build_flp_export_model(project: Project, out_path: str | Path) -> FlpExportModel:
    if len(project.tracks) > MAX_FLP_TRACKS:
        raise ValueError(f"FL Studio export v1 supports up to {MAX_FLP_TRACKS} tracks")

    expanded_clip_count = _expanded_clip_count(project)
    if expanded_clip_count > MAX_FLP_CLIPS:
        raise ValueError(f"FL Studio export v1 supports up to {MAX_FLP_CLIPS} expanded clip placements")

    out_flp = _normalize_flp_path(out_path)
    assets_dir = out_flp.parent / f"{out_flp.name}.assets"
    tracks = tuple(
        FlpTrackAsset(
            track_index=idx,
            track_name=track.name,
            stem_path=str(assets_dir / f"track_{idx:02d}_{_slugify(track.name)}.wav"),
            midi_lane=(idx * 2) + 1,
            audio_lane=(idx * 2) + 2,
        )
        for idx, track in enumerate(project.tracks)
    )
    return FlpExportModel(
        project_name=project.name,
        tempo_bpm=project.tempo_bpm,
        out_flp=str(out_flp),
        assets_dir=str(assets_dir),
        master_ref_path=str(assets_dir / "master_ref.wav"),
        import_midi_path=str(assets_dir / ".project_import.mid"),
        expanded_clip_count=expanded_clip_count,
        tracks=tracks,
    )


def _render_track_stems(project: Project, model: FlpExportModel, *, soundfont: str, mix: dict[str, Any] | None) -> None:
    assets_dir = Path(model.assets_dir)
    assets_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="claw_daw_flp_stems_") as td:
        rendered = export_stems(project, soundfont=soundfont, out_dir=td, mix=mix)
        for rendered_path, track in zip(rendered, model.tracks):
            src = Path(rendered_path)
            dst = Path(track.stem_path)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                dst.unlink()
            src.replace(dst)


def _render_master_reference(
    project: Project,
    model: FlpExportModel,
    *,
    soundfont: str,
    mix: dict[str, Any] | None,
    preset: str,
) -> None:
    with tempfile.TemporaryDirectory(prefix="claw_daw_flp_master_") as td:
        raw_wav = Path(td) / "master_raw.wav"
        render_project_wav(project, soundfont=soundfont, out_wav=str(raw_wav), mix=mix)
        master_wav(str(raw_wav), model.master_ref_path, preset=preset)


def _write_import_midi(project: Project, model: FlpExportModel) -> None:
    out = Path(model.import_midi_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    export_midi(project, out)


def _resolve_fl_studio_app(app_path: str | None) -> Path:
    if app_path:
        p = Path(app_path).expanduser()
        if p.exists():
            return p
        raise RuntimeError(f"FL Studio app not found: {p}")

    candidates = sorted(Path("/Applications").glob("FL Studio*.app"), reverse=True)
    if candidates:
        return candidates[0]
    raise RuntimeError("FL Studio export requires a local FL Studio.app install on macOS")


def _run_osascript(lines: list[str]) -> None:
    cmd = ["osascript"]
    for line in lines:
        cmd.extend(["-e", line])
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def _require_system_events_access() -> None:
    try:
        _run_osascript(['tell application "System Events" to count of every process'])
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").lower()
        stdout = (e.stdout or "").lower()
        msg = stderr or stdout
        if "assistive access" in msg or "not allowed" in msg:
            raise RuntimeError(
                "FL Studio export requires Accessibility access for osascript/System Events. "
                "Enable it in System Settings > Privacy & Security > Accessibility."
            ) from e
        raise


def _wait_for_file(path: str | Path, *, timeout_seconds: float = 30.0) -> None:
    out = Path(path)
    deadline = time.time() + float(timeout_seconds)
    while time.time() < deadline:
        if out.exists() and out.stat().st_size > 0:
            return
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for FL Studio to write: {out}")


def _save_project_with_fl_studio(model: FlpExportModel, *, app_path: str | None) -> None:
    if sys.platform != "darwin":
        raise RuntimeError("FL Studio export currently requires macOS because it uses osascript automation")

    app = _resolve_fl_studio_app(app_path)
    _require_system_events_access()

    out_flp = Path(model.out_flp)
    out_flp.parent.mkdir(parents=True, exist_ok=True)
    out_flp.unlink(missing_ok=True)

    subprocess.run(["open", "-n", "-a", str(app), str(Path(model.import_midi_path))], check=True)

    app_name = app.stem
    out_dir = str(out_flp.parent)
    out_name = out_flp.name
    script = [
        f'tell application "{app_name}" to activate',
        "delay 2",
        'tell application "System Events"',
        '  tell process "OsxFL"',
        "    key code 36",
        "    delay 1",
        "    key code 36",
        "    delay 1",
        '    keystroke "S" using {command down, shift down}',
        "    delay 1",
        '    keystroke "G" using {command down, shift down}',
        "    delay 0.5",
        f'    keystroke "{out_dir}"',
        "    key code 36",
        "    delay 0.5",
        f'    keystroke "{out_name}"',
        "    key code 36",
        "  end tell",
        "end tell",
    ]
    try:
        _run_osascript(script)
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        stdout = (e.stdout or "").strip()
        detail = stderr or stdout or str(e)
        raise RuntimeError(f"FL Studio automation failed: {detail}") from e

    _wait_for_file(out_flp)


def export_fl_studio_project(
    project: Project,
    *,
    out_path: str | Path,
    soundfont: str,
    mix_path: str | None = None,
    preset: str = "clean",
    quality_preset: str = "edm_streaming",
    app_path: str | None = None,
) -> FlpExportResult:
    del quality_preset  # Reserved for future gated FL handoff flow.

    if not soundfont:
        raise RuntimeError("FL Studio export requires a soundfont for asset renders")

    model = build_flp_export_model(project, out_path)
    mix = _load_mix_spec(mix_path)

    _render_track_stems(project, model, soundfont=soundfont, mix=mix)
    _render_master_reference(project, model, soundfont=soundfont, mix=mix, preset=preset)
    _write_import_midi(project, model)
    _save_project_with_fl_studio(model, app_path=app_path)

    return FlpExportResult(
        flp_path=model.out_flp,
        assets_dir=model.assets_dir,
        master_ref_path=model.master_ref_path,
        stem_paths=tuple(track.stem_path for track in model.tracks),
    )
