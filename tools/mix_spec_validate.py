#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import ensure_repo_on_path

ensure_repo_on_path()

from claw_daw.io.project_json import load_project

from mix_utils import classify_track, pick_kick_source_index


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _ok(msg: str) -> str:
    return f"PASS {msg}"


def _fail(msg: str) -> str:
    return f"FAIL {msg}"


def main():
    ap = argparse.ArgumentParser(description="Validate mix spec against best-practice rules.")
    ap.add_argument("project_json", help="Project JSON (out/<name>.json)")
    ap.add_argument("mix_json", help="Mix JSON (tools/<name>.mix.json)")
    ap.add_argument("--min-highpass", type=float, default=100.0)
    ap.add_argument("--mono-min", type=float, default=100.0)
    ap.add_argument("--mono-max", type=float, default=180.0)
    args = ap.parse_args()

    proj = load_project(args.project_json)
    mix = _load_json(Path(args.mix_json))

    tracks_spec = mix.get("tracks") or {}
    busses = mix.get("busses") or {}
    master = mix.get("master") or {}
    sidechain = mix.get("sidechain") or []

    failures = []
    lines = []

    # Sidechain required (kick -> bass).
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
        lines.append(_ok("sidechain kick->bass present"))
    else:
        failures.append("sidechain kick->bass missing")
        lines.append(_fail("sidechain kick->bass missing"))

    # No reverb/delay sends on drums/bass.
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
            lines.append(_fail(f"no reverb/delay on {t.name}"))
        else:
            lines.append(_ok(f"no reverb/delay on {t.name}"))

    # High-pass on non-bass musical tracks.
    for i, t in enumerate(proj.tracks):
        role = classify_track(t.name)
        if role.is_drums or role.is_bass:
            continue
        spec = tracks_spec.get(str(i), {})
        hp = spec.get("highpass_hz", None)
        if hp is None or float(hp) < args.min_highpass:
            failures.append(f"highpass missing/low on {t.name}")
            lines.append(_fail(f"highpass >= {args.min_highpass} on {t.name}"))
        else:
            lines.append(_ok(f"highpass >= {args.min_highpass} on {t.name}"))

    # Mono below on bass bus and master.
    bass_bus = (busses.get("bass") or {})
    bass_mono = bass_bus.get("mono_below_hz", None)
    master_mono = master.get("mono_below_hz", None)

    if bass_mono is not None and args.mono_min <= float(bass_mono) <= args.mono_max:
        lines.append(_ok("bass bus mono_below_hz"))
    else:
        failures.append("bass bus mono_below_hz missing/out of range")
        lines.append(_fail("bass bus mono_below_hz missing/out of range"))

    if master_mono is not None and args.mono_min <= float(master_mono) <= args.mono_max:
        lines.append(_ok("master mono_below_hz"))
    else:
        failures.append("master mono_below_hz missing/out of range")
        lines.append(_fail("master mono_below_hz missing/out of range"))

    # Music bus compression present.
    music_bus = (busses.get("music") or {})
    if (music_bus.get("comp") or None) is not None:
        lines.append(_ok("music bus comp present"))
    else:
        failures.append("music bus comp missing")
        lines.append(_fail("music bus comp missing"))

    print("mix_spec_validate:")
    for ln in lines:
        print(f"- {ln}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
