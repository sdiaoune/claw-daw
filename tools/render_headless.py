#!/usr/bin/env python3
from __future__ import annotations

import argparse

from claw_daw.cli.headless import HeadlessRunner, read_lines_from_path_or_stdin, script_base_dir


def main() -> None:
    ap = argparse.ArgumentParser(description="Run a claw-daw headless script (internal helper).")
    ap.add_argument("--script", required=True, help="Path to .txt script")
    ap.add_argument("--soundfont", default=None, help="Path to GM .sf2")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    script_path = args.script
    lines = read_lines_from_path_or_stdin(script_path)
    base = script_base_dir(script_path)

    runner = HeadlessRunner(soundfont=args.soundfont, strict=args.strict, dry_run=args.dry_run)
    runner.run_lines(lines, base_dir=base)


if __name__ == "__main__":
    main()
