#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import ensure_repo_on_path

ensure_repo_on_path()

from claw_daw.io.project_json import load_project, save_project

from mix_utils import classify_track
from mix_template import build_mix_spec, load_presets


def main():
    ap = argparse.ArgumentParser(description="Assign busses and generate mix spec from a project.")
    ap.add_argument("project_json", help="Project JSON (out/<name>.json)")
    ap.add_argument("--preset", default="edm_streaming", help="Preset name in tools/mix_presets.json")
    ap.add_argument("--presets", default="tools/mix_presets.json", help="Preset file path")
    ap.add_argument("--mix-out", required=True, help="Output mix JSON path")
    ap.add_argument("--out-project", default=None, help="Output project JSON path (defaults to in-place)")
    args = ap.parse_args()

    presets = load_presets(args.presets)
    if args.preset not in presets:
        raise SystemExit(f"Unknown preset: {args.preset}")

    proj = load_project(args.project_json)

    for t in proj.tracks:
        role = classify_track(t.name)
        t.bus = role.bus

    out_project = args.out_project or args.project_json
    save_project(proj, out_project)

    mix = build_mix_spec(proj, presets[args.preset])
    Path(args.mix_out).write_text(json.dumps(mix, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
