#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ensure_repo_on_path

ensure_repo_on_path()

from claw_daw.io.project_json import load_project, save_project

from mix_utils import classify_track, guess_section_scale


def _scale_vel(v: int, factor: float) -> int:
    return max(1, min(127, int(round(v * factor))))


def main():
    ap = argparse.ArgumentParser(description="Apply section-based velocity scaling by pattern name.")
    ap.add_argument("project_json", help="Project JSON to modify")
    ap.add_argument("--out", default=None, help="Output JSON (defaults to in-place)")
    ap.add_argument("--include-drums", action="store_true")
    ap.add_argument("--include-bass", action="store_true")
    args = ap.parse_args()

    proj = load_project(args.project_json)

    for t in proj.tracks:
        role = classify_track(t.name)
        if role.is_drums and not args.include_drums:
            continue
        if role.is_bass and not args.include_bass:
            continue
        for pname, pat in t.patterns.items():
            scale = guess_section_scale(pname)
            if scale is None:
                continue
            for n in pat.notes:
                n.velocity = _scale_vel(n.velocity, scale)

    out_path = args.out or args.project_json
    save_project(proj, out_path)


if __name__ == "__main__":
    main()
