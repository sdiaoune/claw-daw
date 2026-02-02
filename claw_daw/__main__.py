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

    mp = sub.add_parser("midi-ports", help="List available MIDI output ports (for hardware/virtual routing).")
    _ = mp

    play = sub.add_parser("play", help="Play a project to a MIDI output port (real-time).")
    play.add_argument("input", help="Path to a project JSON (.json) or headless script (.txt)")
    play.add_argument("--midi-out", required=True, dest="midi_out", help="MIDI output port name")

    pr = sub.add_parser("prompt", help="Generate a headless script from a natural-language prompt.")
    pr.add_argument("--prompt", default=None, help="Prompt text (or use --prompt-file).")
    pr.add_argument("--prompt-file", default=None, help="Path to a text file containing the prompt.")
    pr.add_argument("--out", required=True, dest="out_prefix", help="Output prefix (writes tools/<out>.txt and out/<out>.*).")
    pr.add_argument("--seed", default=0, type=int, help="Deterministic seed for generation.")
    pr.add_argument("--iters", default=3, type=int, help="Max attempts/iterations (novelty + optional auto-tune loop).")
    pr.add_argument("--max-similarity", default=0.92, type=float, help="Novelty constraint against previous iter (lower = more different).")
    pr.add_argument("--render", action="store_true", help="Also render preview/mp3 using --soundfont.")
    pr.add_argument("--preview-bars", default=8, type=int, help="Preview length in bars (only if --render).")

    gp = sub.add_parser("pack", help="Generate a headless script using a Genre Pack (v1).")
    gp.add_argument("pack", help="Pack name (trap|house|boom_bap).")
    gp.add_argument("--out", required=True, dest="out_prefix", help="Output prefix (writes tools/<out>.txt and out/<out>.*).")
    gp.add_argument("--seed", default=0, type=int, help="Deterministic seed.")
    gp.add_argument("--attempts", default=6, type=int, help="Max attempts (tries to satisfy novelty constraint).")
    gp.add_argument("--max-similarity", default=0.92, type=float, help="Novelty constraint vs previous attempt.")

    sp = sub.add_parser("stylepack", help="Generate/render a beat using a Stylepack (v1) with scoring + iteration.")
    sp.add_argument("stylepack", help="Stylepack name (trap_2020s|boom_bap|house).")
    sp.add_argument("--out", required=True, dest="out_prefix", help="Output prefix (writes tools/<out>.txt and out/<out>.* + report).")
    sp.add_argument("--soundfont", required=True, help="Path to GM SoundFont (.sf2) for renders")
    sp.add_argument("--seed", default=0, type=int, help="Deterministic seed")
    sp.add_argument("--attempts", default=6, type=int, help="Max attempts (score loop)")
    sp.add_argument("--bars", default=32, type=int, help="Target length in bars")
    sp.add_argument("--max-similarity", default=0.92, type=float, help="Novelty constraint vs previous attempt")
    sp.add_argument("--score-threshold", default=0.60, type=float, help="Stop early if score >= threshold")
    sp.add_argument("--knob", action="append", default=[], help="Knob override as key=value (repeatable)")

    dm = sub.add_parser("demos", help="Compile and render golden demos from demos/<style>/*.yaml")
    dm.add_argument("action", choices=["compile", "render"], help="compile scripts or render outputs")
    dm.add_argument("--soundfont", default=None, help="Required for render")

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

    if args.cmd == "midi-ports":
        try:
            import mido

            names = mido.get_output_names()
        except Exception as e:
            raise SystemExit(f"ERROR: Could not list MIDI ports ({e}). Try: pip install python-rtmidi")

        if not names:
            print("(no MIDI output ports found)")
        else:
            for n in names:
                print(n)
        return

    if args.cmd == "play":
        # Real-time MIDI output for auditioning via hardware/virtual ports.
        try:
            import mido
        except Exception as e:
            raise SystemExit(f"ERROR: mido not available ({e})")

        inp = str(args.input)
        if inp.endswith(".json"):
            from claw_daw.io.project_json import load_project
            from claw_daw.io.midi import project_to_midifile

            proj = load_project(inp)
            mf = project_to_midifile(proj)
        else:
            # Treat as headless script: run it to build a project, then play the MIDI.
            from claw_daw.cli.headless import HeadlessRunner
            from claw_daw.io.midi import project_to_midifile

            script = Path(inp).expanduser().resolve()
            base = script.parent
            lines = script.read_text(encoding="utf-8").splitlines()
            r = HeadlessRunner(soundfont=None, strict=True)
            r.run_lines(lines, base_dir=base)
            proj = r.require_project()
            mf = project_to_midifile(proj)

        port_name = str(args.midi_out)
        try:
            outp = mido.open_output(port_name)
        except Exception as e:
            raise SystemExit(f"ERROR: Could not open MIDI output '{port_name}' ({e}). Run: claw-daw midi-ports")

        print(f"playing to MIDI out: {port_name}")
        for msg in mf.play():
            if msg.is_meta:
                continue
            outp.send(msg)
        outp.close()
        return

    if args.cmd == "prompt":
        from claw_daw.prompt.pipeline import generate_from_prompt

        if args.prompt_file:
            prompt_text = Path(args.prompt_file).read_text(encoding="utf-8")
        else:
            prompt_text = args.prompt or ""

        if not prompt_text.strip():
            raise SystemExit("ERROR: provide --prompt or --prompt-file")

        res = generate_from_prompt(
            prompt_text,
            out_prefix=str(args.out_prefix),
            max_iters=int(args.iters),
            seed=int(args.seed),
            max_similarity=float(args.max_similarity),
            soundfont=str(args.soundfont) if getattr(args, "soundfont", None) else None,
            render=bool(args.render),
            preview_bars=int(args.preview_bars),
        )

        print(f"wrote: {res.script_path}")
        if res.preview_path:
            print(f"preview: {res.preview_path}")
        if res.similarities:
            print("similarities:")
            for i, s in enumerate(res.similarities, start=1):
                print(f"- iter{i}: {s:.3f}")
        return

    if args.cmd == "pack":
        from claw_daw.genre_packs.pipeline import generate_from_genre_pack
        from claw_daw.genre_packs.v1 import list_packs_v1

        try:
            res = generate_from_genre_pack(
                str(args.pack),
                out_prefix=str(args.out_prefix),
                max_attempts=int(args.attempts),
                seed=int(args.seed),
                max_similarity=float(args.max_similarity),
            )
        except KeyError as e:
            raise SystemExit(f"ERROR: {e}")
        except Exception as e:
            # surface available packs for UX
            raise SystemExit(f"ERROR: {e}\nAvailable packs: {', '.join(list_packs_v1())}")

        print(f"wrote: {res.script_path}")
        if res.similarities:
            print("similarities:")
            for i, s in enumerate(res.similarities, start=1):
                print(f"- attempt{i}: {s:.3f}")
        return

    if args.cmd == "stylepack":
        from claw_daw.stylepacks.run import run_stylepack
        from claw_daw.stylepacks.types import BeatSpec

        knobs = {}
        for kv in list(getattr(args, "knob", []) or []):
            if "=" not in kv:
                continue
            k, v = kv.split("=", 1)
            k = k.strip()
            v = v.strip()
            # best-effort numeric parsing
            if v.replace(".", "", 1).isdigit():
                v = float(v) if "." in v else int(v)
            knobs[k] = v

        spec = BeatSpec(
            name=str(args.out_prefix),
            stylepack=str(args.stylepack),  # type: ignore[arg-type]
            seed=int(args.seed),
            max_attempts=int(args.attempts),
            length_bars=int(args.bars),
            knobs=knobs,
            score_threshold=float(args.score_threshold),
            max_similarity=float(args.max_similarity),
        )

        rep = run_stylepack(spec, out_prefix=str(args.out_prefix), soundfont=str(args.soundfont))
        print(f"report: {rep}")
        return

    if args.cmd == "demos":
        from claw_daw.stylepacks.tools import compile_demos, render_demos

        action = str(args.action)
        if action == "compile":
            compile_demos()
            return
        if action == "render":
            if not args.soundfont:
                raise SystemExit("ERROR: demos render requires --soundfont")
            render_demos(soundfont=str(args.soundfont))
            return

    parser.print_help()


if __name__ == "__main__":
    main()
