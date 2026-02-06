#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path


def _claw_daw_cmd() -> list[str]:
    env = os.environ.get("CLAW_DAW_CLI")
    if env:
        return shlex.split(env)
    repo_root = Path(__file__).resolve().parents[1]
    if (repo_root / "claw_daw" / "__init__.py").exists():
        return [sys.executable, "-m", "claw_daw"]
    return ["claw-daw"]


def _pick_soundfont() -> str:
    env = os.environ.get("CLAW_DAW_SOUNDFONT")
    if env:
        return env
    p = subprocess.run(_claw_daw_cmd() + ["paths", "--soundfont"], capture_output=True, text=True, check=True)
    for line in (p.stdout or "").splitlines():
        line = line.strip()
        if line:
            return line
    raise RuntimeError("No soundfont found")


def main():
    ap = argparse.ArgumentParser(description="Preview mix gate: render short mix, meter, and gate.")
    ap.add_argument("project_json", help="Project JSON (out/<name>.json)")
    ap.add_argument("mix_json", help="Mix JSON (tools/<name>.mix.json)")
    ap.add_argument("out_prefix", help="Output prefix (e.g., 2026-02-04_song_v1)")
    ap.add_argument("--trim", type=float, default=30.0, help="Preview length in seconds")
    ap.add_argument("--preset", default="edm_streaming", help="Preset name for mix_gate")
    ap.add_argument("--presets", default="tools/mix_presets.json", help="Preset file path")
    args = ap.parse_args()

    sf = _pick_soundfont()

    out_wav = Path("out") / f"{args.out_prefix}.preview.wav"
    out_meter = Path("out") / f"{args.out_prefix}.preview.meter.json"

    script = "\n".join(
        [
            f"open_project {args.project_json}",
            f"export_wav {out_wav} trim={args.trim} preset=clean mix={args.mix_json}",
            f"meter_audio {out_wav} {out_meter}",
        ]
    )

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tf:
        tf.write(script + "\n")
        tmp_path = tf.name

    try:
        subprocess.run(_claw_daw_cmd() + ["--headless", "--soundfont", sf, "--script", tmp_path], check=True)
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass

    gate = subprocess.run(
        [
            "python3",
            "tools/mix_gate.py",
            str(out_meter),
            "--preset",
            args.preset,
            "--presets",
            args.presets,
        ],
        check=False,
    )

    return gate.returncode


if __name__ == "__main__":
    sys.exit(main())
