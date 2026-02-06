#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import ensure_repo_on_path

ensure_repo_on_path()

from claw_daw.io.project_json import load_project

from mix_template import build_mix_spec, load_presets


def main():
    ap = argparse.ArgumentParser(description="Generate a mix spec from a project and preset.")
    ap.add_argument("project_json", help="Project JSON (out/<name>.json)")
    ap.add_argument("--preset", default="edm_streaming", help="Preset name in tools/mix_presets.json")
    ap.add_argument("--presets", default="tools/mix_presets.json", help="Preset file path")
    ap.add_argument("--out", default=None, help="Output mix JSON path")
    ap.add_argument("--print", action="store_true", help="Print JSON to stdout")
    args = ap.parse_args()

    presets = load_presets(args.presets)
    if args.preset not in presets:
        raise SystemExit(f"Unknown preset: {args.preset}")

    proj = load_project(args.project_json)
    mix = build_mix_spec(proj, presets[args.preset])

    out_json = json.dumps(mix, indent=2, sort_keys=True)

    if args.out:
        Path(args.out).write_text(out_json + "\n", encoding="utf-8")
    if args.print or not args.out:
        print(out_json)


if __name__ == "__main__":
    main()
