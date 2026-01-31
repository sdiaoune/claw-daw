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
        notes.append("ffmpeg: MISSING (needed for MP3/M4A encodes)")

    sf2_found = None
    for p in _default_soundfont_paths():
        if Path(p).exists():
            sf2_found = p
            break
    if sf2_found:
        notes.append(f"soundfont: OK ({sf2_found})")
    else:
        ok = False
        notes.append(
            "soundfont: MISSING (install a GM .sf2 or pass --soundfont /path/to.sf2 when exporting)"
        )

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
            "This repo is under active iteration. Some features may be incomplete in early versions.\n"
            "Docs: https://sdiaoune.github.io/claw-daw/\n"
        ),
    )

    p.add_argument(
        "--version",
        action="store_true",
        help="Print version and exit.",
    )

    sub = p.add_subparsers(dest="cmd")

    sub.add_parser(
        "doctor",
        help="Check for required system dependencies (fluidsynth/ffmpeg/soundfont).",
    )

    paths = sub.add_parser("paths", help="Print common paths used by claw-daw.")
    paths.add_argument(
        "--soundfont",
        action="store_true",
        help="Print common GM SoundFont (.sf2) locations.",
    )

    return p


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)

    parser = build_parser()
    args = parser.parse_args(argv)

    # Version: best-effort (don’t hard-fail if metadata isn’t available).
    if getattr(args, "version", False):
        try:
            from importlib.metadata import version

            v = version("claw-daw")
        except Exception:
            v = "0.0.0"
        print(f"claw-daw {v}")
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

    # Default: show help.
    parser.print_help()


if __name__ == "__main__":
    main()
