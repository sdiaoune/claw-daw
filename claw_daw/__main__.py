from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DoctorResult:
    ok: bool
    notes: list[str]


def _which(cmd: str) -> str | None:
    return shutil.which(cmd)


def _default_soundfont_paths() -> list[str]:
    return [
        "/usr/share/sounds/sf2/default-GM.sf2",
        "/usr/share/sounds/sf2/FluidR3_GM.sf2",
        "/usr/share/sounds/sf2/GeneralUser-GS-v1.471.sf2",
    ]


def _doctor() -> DoctorResult:
    notes: list[str] = []

    fluidsynth = _which("fluidsynth")
    ffmpeg = _which("ffmpeg")

    ok = True

    if fluidsynth:
        notes.append(f"fluidsynth: OK ({fluidsynth})")
    else:
        ok = False
        notes.append("fluidsynth: MISSING (needed for MIDI→WAV renders)")

    if ffmpeg:
        notes.append(f"ffmpeg: OK ({ffmpeg})")
    else:
        ok = False
        notes.append("ffmpeg: MISSING (needed for MP3 encodes)")

    sf2_found = None
    for p in _default_soundfont_paths():
        if Path(p).exists():
            sf2_found = p
            break
    if sf2_found:
        notes.append(f"soundfont: OK ({sf2_found})")
    else:
        ok = False
        notes.append("soundfont: MISSING (install a GM .sf2)")

    notes.append(f"python: {sys.version.split()[0]}")
    notes.append(f"platform: {sys.platform}")

    return DoctorResult(ok=ok, notes=notes)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="claw-daw",
        add_help=True,
        formatter_class=argparse.RawTextHelpFormatter,
        description=(
            "claw-daw — offline, deterministic, terminal-first MIDI DAW\n\n"
            "Docs: https://www.clawdaw.com/\n"
        ),
    )

    p.add_argument("--version", action="store_true", help="Print version and exit.")

    # Headless mode (compat with docs)
    p.add_argument(
        "--headless",
        action="store_true",
        help="Run a headless script (new_project/add_track/new_pattern/... + export_*).",
    )
    p.add_argument("--soundfont", default=None, help="Path to GM SoundFont (.sf2) for renders")
    p.add_argument("--script", default=None, help="Path to headless script (.txt)")

    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("doctor", help="Check for required deps (fluidsynth/ffmpeg/soundfont).")

    paths = sub.add_parser("paths", help="Print common paths used by claw-daw.")
    paths.add_argument("--soundfont", action="store_true", help="Print common GM SoundFont (.sf2) locations.")

    return p


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)

    parser = build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "version", False):
        try:
            from importlib.metadata import version

            v = version("claw-daw")
        except Exception:
            v = "0.0.0"
        print(f"claw-daw {v}")
        return

    if args.headless:
        if not args.script:
            raise SystemExit("ERROR: --headless requires --script <path>")
        if not args.soundfont:
            raise SystemExit("ERROR: --headless requires --soundfont <path-to.sf2>")

        # Use the agent-friendly headless runner (supports bar:beat, transforms, select/apply, streaming exports).
        from claw_daw.cli.headless import HeadlessRunner

        script = Path(args.script).expanduser().resolve()
        base = script.parent
        lines = script.read_text(encoding="utf-8").splitlines()

        r = HeadlessRunner(soundfont=str(Path(args.soundfont).expanduser().resolve()), strict=True)
        r.run_lines(lines, base_dir=base)
        return

    if args.cmd == "doctor":
        res = _doctor()
        status = "OK" if res.ok else "MISSING_DEPS"
        print(f"claw-daw doctor: {status}")
        for n in res.notes:
            print(f"- {n}")
        if not res.ok:
            print("\nLinux (Debian/Ubuntu): sudo apt-get install fluidsynth ffmpeg fluid-soundfont-gm")
            print("macOS: brew install fluidsynth ffmpeg")
        return

    if args.cmd == "paths":
        if args.soundfont:
            for pth in _default_soundfont_paths():
                print(pth)
        else:
            print(f"cwd: {os.getcwd()}")
            print("config: (not implemented)")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
