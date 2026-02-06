from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from claw_daw.audio.metering import analyze_metering
from claw_daw.cli.headless import HeadlessRunner
from claw_daw.io.project_json import load_project, save_project
from claw_daw.model.types import Project
from claw_daw.util.soundfont import find_default_soundfont


@dataclass(frozen=True)
class TrackRole:
    role: str
    bus: str
    is_drums: bool
    is_bass: bool
    is_kick: bool


@dataclass(frozen=True)
class QualityWorkflowError(RuntimeError):
    report: dict[str, Any]

    def __str__(self) -> str:
        return str(self.report.get("error") or "quality workflow failed")


def _has_any(name: str, tokens: Iterable[str]) -> bool:
    return any(t in name for t in tokens)


def classify_track(name: str) -> TrackRole:
    n = (name or "").strip().lower()

    drum_tokens = ["drum", "perc", "kick", "snare", "clap", "hat", "hh", "ride", "cym", "tom", "shaker", "rim"]
    bass_tokens = ["bass", "sub", "808"]
    vocal_tokens = ["vocal", "vox", "voice", "choir"]
    lead_tokens = ["lead", "hook"]
    pluck_tokens = ["pluck", "arp", "seq"]
    pad_tokens = ["pad", "string", "strings", "wash", "atmo", "atmos"]
    keys_tokens = ["key", "keys", "chord", "piano", "organ", "synth", "stab"]
    fx_tokens = ["fx", "rise", "riser", "impact", "sweep", "noise", "down", "uplifter", "drop"]

    is_drums = _has_any(n, drum_tokens)
    is_bass = _has_any(n, bass_tokens)
    is_vocal = _has_any(n, vocal_tokens)
    is_kick = "kick" in n

    if is_drums:
        return TrackRole(role="drums", bus="drums", is_drums=True, is_bass=False, is_kick=is_kick)
    if is_bass:
        return TrackRole(role="bass", bus="bass", is_drums=False, is_bass=True, is_kick=False)
    if is_vocal:
        return TrackRole(role="vox", bus="vox", is_drums=False, is_bass=False, is_kick=False)
    if _has_any(n, lead_tokens):
        return TrackRole(role="lead", bus="music", is_drums=False, is_bass=False, is_kick=False)
    if _has_any(n, pluck_tokens):
        return TrackRole(role="pluck", bus="music", is_drums=False, is_bass=False, is_kick=False)
    if _has_any(n, pad_tokens):
        return TrackRole(role="pad", bus="music", is_drums=False, is_bass=False, is_kick=False)
    if _has_any(n, keys_tokens):
        return TrackRole(role="keys", bus="music", is_drums=False, is_bass=False, is_kick=False)
    if _has_any(n, fx_tokens):
        return TrackRole(role="fx", bus="music", is_drums=False, is_bass=False, is_kick=False)
    return TrackRole(role="music", bus="music", is_drums=False, is_bass=False, is_kick=False)


def pick_kick_source_index(tracks: list[Any]) -> int | None:
    kick_idx = None
    drum_idx = None
    for i, t in enumerate(tracks):
        role = classify_track(getattr(t, "name", ""))
        if role.is_kick:
            kick_idx = i
            break
        if role.is_drums and drum_idx is None:
            drum_idx = i
    return kick_idx if kick_idx is not None else drum_idx


def track_is_drum_role_capable(track: Any) -> bool:
    try:
        if getattr(track, "channel", None) == 9:
            return True
    except Exception:
        pass
    try:
        if getattr(track, "sampler", None) == "drums":
            return True
    except Exception:
        pass
    try:
        if getattr(track, "sample_pack", None) is not None:
            return True
    except Exception:
        pass
    try:
        if getattr(track, "drum_kit", None):
            return True
    except Exception:
        pass
    return False


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_presets(path: str | Path) -> dict[str, Any]:
    return _load_json(path)


def _normalize_out_prefix(out_prefix: str) -> str:
    s = str(out_prefix or "").strip().replace("\\", "/")
    if s.startswith("./"):
        s = s[2:]
    if s.startswith("out/"):
        s = s[4:]
    for ext in (".json", ".mp3", ".mid", ".wav"):
        if s.endswith(ext):
            s = s[: -len(ext)]
    s = re.sub(r"^/+", "", s)
    s = re.sub(r"/+$", "", s)
    if not s:
        raise ValueError("empty out prefix")
    return s


def build_mix_spec(project: Project, preset: dict[str, Any]) -> dict[str, Any]:
    mix_def = preset.get("mix") or {}
    role_defs = mix_def.get("roles") or {}

    mix = {
        "tracks": {},
        "returns": mix_def.get("returns") or {},
        "busses": mix_def.get("busses") or {},
        "master": mix_def.get("master") or {},
        "sidechain": [],
    }

    for i, t in enumerate(project.tracks):
        role = classify_track(t.name)
        spec = dict(role_defs.get(role.role) or role_defs.get("music") or {})
        mix["tracks"][str(i)] = spec

    sc_def = mix_def.get("sidechain") or {}
    targets = sc_def.get("targets") or ["bass"]
    params = sc_def.get("params") or {"threshold_db": -24, "ratio": 6, "attack_ms": 5, "release_ms": 120}

    kick_idx = pick_kick_source_index(project.tracks)
    if kick_idx is not None:
        src_track = project.tracks[kick_idx]
        use_src_role = track_is_drum_role_capable(src_track)
        for i, t in enumerate(project.tracks):
            role = classify_track(t.name)
            if role.role in targets:
                sc = {"src": kick_idx, "dst": i}
                if use_src_role:
                    sc["src_role"] = "kick"
                sc.update(params)
                mix["sidechain"].append(sc)

    return mix


def prepare_mix_spec(
    project_json: str,
    *,
    preset: str,
    presets_path: str = "tools/mix_presets.json",
    mix_out: str,
    out_project: str | None = None,
) -> tuple[str, str]:
    presets = _load_presets(presets_path)
    if preset not in presets:
        raise ValueError(f"unknown preset: {preset}")

    proj = load_project(project_json)
    for t in proj.tracks:
        t.bus = classify_track(t.name).bus

    out_proj = out_project or project_json
    save_project(proj, out_proj)

    mix = build_mix_spec(proj, presets[preset])
    _write_json(mix_out, mix)
    return out_proj, mix_out


def apply_section_gain(
    project_json: str,
    *,
    out_project: str | None = None,
    include_drums: bool = False,
    include_bass: bool = False,
) -> str:
    def _guess_section_scale(pattern_name: str) -> float | None:
        name = (pattern_name or "").lower()
        rules = [
            (r"breakdown|break", 0.75),
            (r"intro|outro", 0.85),
            (r"build|rise", 0.90),
            (r"verse", 0.90),
            (r"drop|chorus|hook", 1.0),
        ]
        for pat, scale in rules:
            if re.search(pat, name):
                return scale
        return None

    def _scale_vel(v: int, factor: float) -> int:
        return max(1, min(127, int(round(v * factor))))

    proj = load_project(project_json)
    for t in proj.tracks:
        role = classify_track(t.name)
        if role.is_drums and not include_drums:
            continue
        if role.is_bass and not include_bass:
            continue
        for pname, pat in t.patterns.items():
            scale = _guess_section_scale(pname)
            if scale is None:
                continue
            for n in pat.notes:
                n.velocity = _scale_vel(n.velocity, scale)

    out_path = out_project or project_json
    save_project(proj, out_path)
    return out_path


def validate_mix_spec(
    project_json: str,
    mix_json: str,
    *,
    min_highpass: float = 100.0,
    mono_min: float = 100.0,
    mono_max: float = 180.0,
) -> tuple[bool, list[str]]:
    proj = load_project(project_json)
    mix = _load_json(mix_json)

    tracks_spec = mix.get("tracks") or {}
    busses = mix.get("busses") or {}
    master = mix.get("master") or {}
    sidechain = mix.get("sidechain") or []

    failures: list[str] = []
    checks: list[str] = []

    kick_idx = pick_kick_source_index(proj.tracks)
    bass_idxs = [i for i, t in enumerate(proj.tracks) if classify_track(t.name).is_bass]
    has_sc = False
    for sc in sidechain:
        try:
            if kick_idx is not None and int(sc.get("src")) == kick_idx and int(sc.get("dst")) in bass_idxs:
                has_sc = True
                break
        except Exception:
            continue
    if has_sc:
        checks.append("PASS sidechain kick->bass present")
    else:
        failures.append("sidechain kick->bass missing")
        checks.append("FAIL sidechain kick->bass missing")

    for i, t in enumerate(proj.tracks):
        role = classify_track(t.name)
        if not (role.is_drums or role.is_bass):
            continue
        spec = tracks_spec.get(str(i), {})
        sends = spec.get("sends") or {}
        bad = False
        for k in ("reverb", "delay"):
            try:
                if float(sends.get(k, 0.0)) > 0.0:
                    bad = True
            except Exception:
                pass
        if bad:
            failures.append(f"reverb/delay on {t.name}")
            checks.append(f"FAIL no reverb/delay on {t.name}")
        else:
            checks.append(f"PASS no reverb/delay on {t.name}")

    for i, t in enumerate(proj.tracks):
        role = classify_track(t.name)
        if role.is_drums or role.is_bass:
            continue
        spec = tracks_spec.get(str(i), {})
        hp = spec.get("highpass_hz", None)
        if hp is None or float(hp) < min_highpass:
            failures.append(f"highpass missing/low on {t.name}")
            checks.append(f"FAIL highpass >= {min_highpass} on {t.name}")
        else:
            checks.append(f"PASS highpass >= {min_highpass} on {t.name}")

    bass_bus = busses.get("bass") or {}
    bass_mono = bass_bus.get("mono_below_hz", None)
    master_mono = master.get("mono_below_hz", None)

    if bass_mono is not None and mono_min <= float(bass_mono) <= mono_max:
        checks.append("PASS bass bus mono_below_hz")
    else:
        failures.append("bass bus mono_below_hz missing/out of range")
        checks.append("FAIL bass bus mono_below_hz missing/out of range")

    if master_mono is not None and mono_min <= float(master_mono) <= mono_max:
        checks.append("PASS master mono_below_hz")
    else:
        failures.append("master mono_below_hz missing/out of range")
        checks.append("FAIL master mono_below_hz missing/out of range")

    music_bus = busses.get("music") or {}
    if (music_bus.get("comp") or None) is not None:
        checks.append("PASS music bus comp present")
    else:
        failures.append("music bus comp missing")
        checks.append("FAIL music bus comp missing")

    return len(failures) == 0, checks


def _f(v: Any) -> float | None:
    try:
        return float(v)
    except Exception:
        return None


def gate_master_meter(
    meter_json: str,
    *,
    preset: str,
    presets_path: str = "tools/mix_presets.json",
    crest_min: float = 6.0,
) -> tuple[bool, list[str]]:
    data = _load_json(meter_json)
    presets = _load_presets(presets_path)
    if preset not in presets:
        raise ValueError(f"unknown preset: {preset}")

    gates = (presets.get(preset) or {}).get("gates") or {}
    master = gates.get("master") or {}

    lufs_min = master.get("lufs_min", -15.5)
    lufs_max = master.get("lufs_max", -12.5)
    true_peak_max = master.get("true_peak_max", -1.0)
    stereo_corr_min = master.get("stereo_corr_min", -0.2)
    stereo_balance_max = master.get("stereo_balance_max", 1.5)
    dc_offset_max = master.get("dc_offset_max", 0.02)
    spectral_tilt_min = master.get("spectral_tilt_min", None)
    spectral_tilt_max = master.get("spectral_tilt_max", None)

    metrics = {
        "integrated_lufs": _f(data.get("integrated_lufs")),
        "true_peak_dbtp": _f(data.get("true_peak_dbtp")),
        "crest_factor_db": _f(data.get("crest_factor_db")),
        "stereo_correlation": _f(data.get("stereo_correlation")),
        "stereo_balance_db": _f(data.get("stereo_balance_db")),
        "dc_offset": _f(data.get("dc_offset")),
        "spectral_tilt_db": _f(data.get("spectral_tilt_db")),
    }

    checks: list[tuple[str, bool, str]] = []

    lufs = metrics["integrated_lufs"]
    if lufs is None:
        checks.append(("integrated_lufs", False, "missing"))
    else:
        checks.append(("integrated_lufs", lufs_min <= lufs <= lufs_max, f"{lufs:.2f} (target {lufs_min}..{lufs_max})"))

    tp = metrics["true_peak_dbtp"]
    if tp is None:
        checks.append(("true_peak_dbtp", False, "missing"))
    else:
        checks.append(("true_peak_dbtp", tp <= true_peak_max, f"{tp:.2f} dBTP (<= {true_peak_max})"))

    cf = metrics["crest_factor_db"]
    if cf is None:
        checks.append(("crest_factor_db", False, "missing"))
    else:
        checks.append(("crest_factor_db", cf >= crest_min, f"{cf:.2f} dB (>= {crest_min})"))

    corr = metrics["stereo_correlation"]
    if corr is None:
        checks.append(("stereo_correlation", False, "missing"))
    else:
        checks.append(("stereo_correlation", corr >= stereo_corr_min, f"{corr:.2f} (>= {stereo_corr_min})"))

    bal = metrics["stereo_balance_db"]
    if bal is None:
        checks.append(("stereo_balance_db", False, "missing"))
    else:
        checks.append(("stereo_balance_db", abs(bal) <= stereo_balance_max, f"{bal:.2f} dB (<= {stereo_balance_max})"))

    dc = metrics["dc_offset"]
    if dc is None:
        checks.append(("dc_offset", False, "missing"))
    else:
        checks.append(("dc_offset", abs(dc) <= dc_offset_max, f"{dc:.4f} (<= {dc_offset_max})"))

    tilt = metrics["spectral_tilt_db"]
    if spectral_tilt_min is not None or spectral_tilt_max is not None:
        if tilt is None:
            checks.append(("spectral_tilt_db", False, "missing"))
        else:
            ok = True
            if spectral_tilt_min is not None and tilt < spectral_tilt_min:
                ok = False
            if spectral_tilt_max is not None and tilt > spectral_tilt_max:
                ok = False
            checks.append(("spectral_tilt_db", ok, f"{tilt:.2f} dB (target {spectral_tilt_min}..{spectral_tilt_max})"))

    out = [f"{'PASS' if ok else 'FAIL'} {name}: {detail}" for name, ok, detail in checks]
    return all(ok for _, ok, _ in checks), out


def _role_from_filename(name: str) -> str:
    base = name.lower().replace(".wav", "")
    base = base.split("_", 1)[1] if "_" in base and base.split("_", 1)[0].isdigit() else base
    return classify_track(base).role


def gate_stems(
    stem_dir: str,
    *,
    bus_dir: str | None,
    preset: str,
    presets_path: str = "tools/mix_presets.json",
    lufs_guidance: bool = True,
) -> tuple[bool, list[str]]:
    presets = _load_presets(presets_path)
    if preset not in presets:
        raise ValueError(f"unknown preset: {preset}")

    gates = (presets.get(preset) or {}).get("gates") or {}
    stems_gate = gates.get("stems") or {}

    true_peak_max = stems_gate.get("true_peak_max", -3.0)
    peak_max = stems_gate.get("peak_max", -3.0)
    crest_min = stems_gate.get("crest_min", 3.0)
    stereo_corr_min = stems_gate.get("stereo_corr_min", -0.5)
    stereo_balance_max = stems_gate.get("stereo_balance_max", 4.0)
    dc_offset_max = stems_gate.get("dc_offset_max", 0.02)
    guidance = stems_gate.get("lufs_guidance") or {}

    files = sorted(Path(stem_dir).glob("*.wav"))
    if bus_dir:
        files += sorted(Path(bus_dir).glob("*.wav"))

    if not files:
        return False, ["FAIL no stems/busses found"]

    lines: list[str] = []
    all_ok = True

    for wav in files:
        rep = analyze_metering(str(wav), include_spectral=False)
        metrics = {
            "integrated_lufs": _f(rep.integrated_lufs),
            "true_peak_dbtp": _f(rep.true_peak_dbtp),
            "peak_dbfs": _f(rep.peak_dbfs),
            "crest_factor_db": _f(rep.crest_factor_db),
            "stereo_correlation": _f(rep.stereo_correlation),
            "stereo_balance_db": _f(rep.stereo_balance_db),
            "dc_offset": _f(rep.dc_offset),
        }

        checks: list[tuple[str, bool, str]] = []

        tp = metrics["true_peak_dbtp"]
        checks.append(("true_peak_dbtp", tp is not None and tp <= true_peak_max, "missing" if tp is None else f"{tp:.2f} dBTP (<= {true_peak_max})"))

        pk = metrics["peak_dbfs"]
        checks.append(("peak_dbfs", pk is not None and pk <= peak_max, "missing" if pk is None else f"{pk:.2f} dBFS (<= {peak_max})"))

        cf = metrics["crest_factor_db"]
        checks.append(("crest_factor_db", cf is not None and cf >= crest_min, "missing" if cf is None else f"{cf:.2f} dB (>= {crest_min})"))

        corr = metrics["stereo_correlation"]
        checks.append(("stereo_correlation", corr is not None and corr >= stereo_corr_min, "missing" if corr is None else f"{corr:.2f} (>= {stereo_corr_min})"))

        bal = metrics["stereo_balance_db"]
        checks.append(("stereo_balance_db", bal is not None and abs(bal) <= stereo_balance_max, "missing" if bal is None else f"{bal:.2f} dB (<= {stereo_balance_max})"))

        dc = metrics["dc_offset"]
        checks.append(("dc_offset", dc is not None and abs(dc) <= dc_offset_max, "missing" if dc is None else f"{dc:.4f} (<= {dc_offset_max})"))

        if lufs_guidance and guidance:
            role = _role_from_filename(wav.name)
            guide = guidance.get(role) or guidance.get("music")
            if guide:
                lufs = metrics["integrated_lufs"]
                if lufs is None:
                    checks.append(("integrated_lufs", False, "missing"))
                else:
                    ok = float(guide["min"]) <= lufs <= float(guide["max"])
                    checks.append(("integrated_lufs", ok, f"{lufs:.2f} (target {guide['min']}..{guide['max']})"))

        file_ok = all(ok for _, ok, _ in checks)
        all_ok = all_ok and file_ok
        lines.append(f"{'PASS' if file_ok else 'FAIL'} {wav.name}")
        for name, ok, detail in checks:
            lines.append(f"  {'PASS' if ok else 'FAIL'} {name}: {detail}")

    return all_ok, lines


def _pick_soundfont(soundfont: str | None) -> str:
    if soundfont:
        return str(Path(soundfont).expanduser().resolve())
    env_sf = os.environ.get("CLAW_DAW_SOUNDFONT")
    if env_sf:
        return str(Path(env_sf).expanduser().resolve())
    found = find_default_soundfont()
    if found:
        return str(Path(found).expanduser().resolve())
    raise RuntimeError("no soundfont available; pass --soundfont or set CLAW_DAW_SOUNDFONT")


def _run_headless_lines(lines: list[str], *, soundfont: str, base_dir: Path | None = None) -> None:
    r = HeadlessRunner(soundfont=soundfont, strict=True, dry_run=False)
    r.run_lines(lines, base_dir=base_dir)


def run_quality_workflow(
    *,
    project_json: str,
    out_prefix: str,
    soundfont: str | None = None,
    preset: str = "edm_streaming",
    presets_path: str = "tools/mix_presets.json",
    mix_out: str | None = None,
    out_dir: str = "out",
    tools_dir: str = "tools",
    section_gain: bool = False,
    preview_trim: float = 30.0,
    lufs_guidance: bool = True,
) -> dict[str, Any]:
    out_name = _normalize_out_prefix(out_prefix)
    out_dir_path = Path(out_dir)
    project_path = str(Path(project_json))
    mix_path = mix_out or str(Path(tools_dir) / f"{out_name}.mix.json")

    report: dict[str, Any] = {
        "ok": False,
        "out_prefix": out_name,
        "preset": preset,
        "project_json": project_path,
        "mix_json": mix_path,
        "steps": [],
    }

    sf = _pick_soundfont(soundfont)
    report["soundfont"] = sf

    try:
        prepare_mix_spec(project_path, preset=preset, presets_path=presets_path, mix_out=mix_path, out_project=project_path)
        report["steps"].append({"step": "mix_prepare", "ok": True, "detail": f"wrote {mix_path}"})

        if section_gain:
            apply_section_gain(project_path)
            report["steps"].append({"step": "section_gain", "ok": True, "detail": "applied"})

        ok, checks = validate_mix_spec(project_path, mix_path)
        report["steps"].append({"step": "mix_spec_validate", "ok": ok, "checks": checks})
        if not ok:
            raise QualityWorkflowError({**report, "error": "mix_spec_validate failed"})

        preview_wav = out_dir_path / f"{out_name}.preview.wav"
        preview_meter = out_dir_path / f"{out_name}.preview.meter.json"
        _run_headless_lines(
            [
                f"open_project {project_path}",
                f"export_wav {preview_wav} trim={float(preview_trim)} preset=clean mix={mix_path}",
                f"meter_audio {preview_wav} {preview_meter}",
            ],
            soundfont=sf,
            base_dir=Path.cwd(),
        )

        ok, checks = gate_master_meter(str(preview_meter), preset=preset, presets_path=presets_path)
        report["steps"].append({"step": "preview_gate", "ok": ok, "checks": checks, "meter": str(preview_meter)})
        if not ok:
            raise QualityWorkflowError({**report, "error": "preview_gate failed"})

        _run_headless_lines(
            [
                f"open_project {project_path}",
                f"export_package {out_name} preset=clean mix={mix_path} stems=1 busses=1 meter=1",
            ],
            soundfont=sf,
            base_dir=Path.cwd(),
        )
        report["steps"].append({"step": "export_package", "ok": True})

        master_meter = out_dir_path / f"{out_name}.meter.json"
        ok, checks = gate_master_meter(str(master_meter), preset=preset, presets_path=presets_path)
        report["steps"].append({"step": "mix_gate", "ok": ok, "checks": checks, "meter": str(master_meter)})
        if not ok:
            raise QualityWorkflowError({**report, "error": "mix_gate failed"})

        stem_dir = out_dir_path / f"{out_name}_stems"
        bus_dir = out_dir_path / f"{out_name}_busses"
        ok, checks = gate_stems(
            str(stem_dir),
            bus_dir=str(bus_dir),
            preset=preset,
            presets_path=presets_path,
            lufs_guidance=lufs_guidance,
        )
        report["steps"].append({"step": "mix_gate_stems", "ok": ok, "checks": checks})
        if not ok:
            raise QualityWorkflowError({**report, "error": "mix_gate_stems failed"})

        report["ok"] = True
        return report
    except QualityWorkflowError:
        raise
    except Exception as e:
        raise QualityWorkflowError({**report, "error": str(e)}) from e
