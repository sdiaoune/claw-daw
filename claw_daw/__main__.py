from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from claw_daw.util.soundfont import default_soundfont_paths, find_default_soundfont


@dataclass
class DoctorResult:
    ok: bool
    notes: list[str]


def _which(cmd: str) -> str | None:
    return shutil.which(cmd)


def _doctor(*, audio: str | None = None) -> DoctorResult:
    notes: list[str] = []

    fluidsynth = _which("fluidsynth")
    ffmpeg = _which("ffmpeg")
    ffprobe = _which("ffprobe")

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
        notes.append("ffmpeg: MISSING (needed for MP3 encodes + metering)")

    if ffprobe:
        notes.append(f"ffprobe: OK ({ffprobe})")
    else:
        ok = False
        notes.append("ffprobe: MISSING (needed for metering)")

    sf2_found = find_default_soundfont()
    if sf2_found:
        notes.append(f"soundfont: OK ({sf2_found})")
    else:
        ok = False
        notes.append("soundfont: MISSING (install a GM .sf2)")

    notes.append(f"python: {sys.version.split()[0]}")
    notes.append(f"platform: {sys.platform}")

    # Optional audio QA
    if audio:
        try:
            from claw_daw.audio.metering import analyze_metering
            from claw_daw.audio.sanity import analyze_mix_sanity

            m = analyze_metering(audio, include_spectral=True)
            s = analyze_mix_sanity(audio)

            notes.append(f"audio.integrated_lufs: {m.integrated_lufs}")
            notes.append(f"audio.shortterm_lufs: {m.shortterm_lufs}")
            notes.append(f"audio.true_peak_dbtp: {m.true_peak_dbtp}")
            notes.append(f"audio.crest_factor_db: {m.crest_factor_db}")
            notes.append(f"audio.stereo_correlation: {m.stereo_correlation}")
            notes.append(f"audio.stereo_balance_db: {m.stereo_balance_db}")
            notes.append(f"audio.spectral_tilt_db: {m.spectral_tilt_db}")
            notes.append(f"audio.sanity_score: {s.score:.2f}")
            for r in s.reasons[:6]:
                notes.append(f"audio.warn: {r}")
        except Exception as e:
            ok = False
            notes.append(f"audio: ERROR ({e})")

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
    d = sub.add_parser("doctor", help="Check for required deps (fluidsynth/ffmpeg/soundfont) and optional audio QA.")
    d.add_argument("--audio", default=None, help="Optional: path to audio file to meter + sanity-check.")

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
    pr.add_argument("--render", action="store_true", help="Render with deterministic quality workflow using --soundfont.")
    pr.add_argument("--preview-bars", default=8, type=int, help="Preview length in bars (only if --render).")
    pr.add_argument("--quality-preset", default="edm_streaming", help="Quality gate preset used when --render is enabled.")
    pr.add_argument("--quality-presets", default="tools/mix_presets.json", help="Path to mix preset definitions.")
    pr.add_argument("--section-gain", action="store_true", help="Apply section-based velocity shaping before gated export.")

    gp = sub.add_parser("pack", help="Generate a headless script using a Genre Pack (v1).")
    gp.add_argument("pack", help="Pack name (trap|house|boom_bap).")
    gp.add_argument("--out", required=True, dest="out_prefix", help="Output prefix (writes tools/<out>.txt and out/<out>.*).")
    gp.add_argument("--seed", default=0, type=int, help="Deterministic seed.")
    gp.add_argument("--attempts", default=6, type=int, help="Max attempts (tries to satisfy novelty constraint).")
    gp.add_argument("--max-similarity", default=0.92, type=float, help="Novelty constraint vs previous attempt.")
    gp.add_argument("--render", action="store_true", help="Also render and run mandatory quality gates.")
    gp.add_argument("--soundfont", default=None, help="Optional GM SoundFont path for quality render.")
    gp.add_argument("--quality-preset", default="edm_streaming", help="Quality gate preset used with --render.")
    gp.add_argument("--quality-presets", default="tools/mix_presets.json", help="Path to mix preset definitions.")
    gp.add_argument("--section-gain", action="store_true", help="Apply section-based velocity shaping before gated export.")

    sp = sub.add_parser("stylepack", help="Generate/render a beat using a Stylepack (v1) with scoring + gated export.")
    sp.add_argument("stylepack", help="Stylepack name (trap_2020s|boom_bap|house).")
    sp.add_argument("--out", required=True, dest="out_prefix", help="Output prefix (writes tools/<out>.txt and out/<out>.* + report).")
    sp.add_argument("--soundfont", required=True, help="Path to GM SoundFont (.sf2) for renders")
    sp.add_argument("--seed", default=0, type=int, help="Deterministic seed")
    sp.add_argument("--attempts", default=6, type=int, help="Max attempts (score loop)")
    sp.add_argument("--bars", default=32, type=int, help="Target length in bars")
    sp.add_argument("--max-similarity", default=0.92, type=float, help="Novelty constraint vs previous attempt")
    sp.add_argument("--score-threshold", default=0.60, type=float, help="Stop early if score >= threshold")
    sp.add_argument("--knob", action="append", default=[], help="Knob override as key=value (repeatable)")
    sp.add_argument("--quality-preset", default="edm_streaming", help="Quality gate preset for final export.")
    sp.add_argument("--quality-presets", default="tools/mix_presets.json", help="Path to mix preset definitions.")
    sp.add_argument("--section-gain", action="store_true", help="Apply section-based velocity shaping before gated export.")

    ar = sub.add_parser(
        "arrange-spec",
        help="Apply a section/cue arrangement spec (YAML/JSON) to an existing project.",
    )
    ar.add_argument("spec", help="Path to arrangement spec (.yaml/.yml/.json)")
    ar.add_argument("--in", dest="inp", required=True, help="Input project JSON")
    ar.add_argument("--out", dest="out", required=True, help="Output project JSON")
    ar.add_argument(
        "--keep-existing-clips",
        action="store_true",
        help="Do not clear existing clips before placing arrangement (advanced).",
    )

    dm = sub.add_parser("demos", help="Compile and render golden demos from demos/<style>/*.yaml")
    dm.add_argument("action", choices=["compile", "render"], help="compile scripts or render outputs")
    dm.add_argument("--soundfont", default=None, help="Required for render")

    ql = sub.add_parser("quality", help="Run full deterministic mix+gate workflow for an existing project JSON.")
    ql.add_argument("project_json", help="Path to project JSON (usually out/<name>.json)")
    ql.add_argument("--out", required=True, dest="out_prefix", help="Output prefix (<name> or out/<name>)")
    ql.add_argument("--soundfont", default=None, help="Optional GM SoundFont path")
    ql.add_argument("--preset", default="edm_streaming", help="Quality gate preset")
    ql.add_argument("--presets", default="tools/mix_presets.json", help="Path to mix preset definitions")
    ql.add_argument("--mix-out", default=None, help="Where to write mix JSON (defaults to tools/<name>.mix.json)")
    ql.add_argument("--section-gain", action="store_true", help="Apply section-based velocity shaping before gated export.")
    ql.add_argument("--preview-trim", type=float, default=30.0, help="Preview length in seconds for fail-fast gate.")
    ql.add_argument("--no-lufs-guidance", action="store_true", help="Disable per-role LUFS guidance in stem gate.")

    return p


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)

    parser = build_parser()
    args = parser.parse_args(argv)

    def _normalize_out_prefix(prefix: str) -> str:
        s = str(prefix or "").strip().replace("\\", "/")
        if s.startswith("./"):
            s = s[2:]
        if s.startswith("out/"):
            s = s[4:]
        return s.strip("/") or s

    def _print_quality_report(report: dict) -> None:
        print(f"quality: {'PASS' if report.get('ok') else 'FAIL'} preset={report.get('preset')}")
        for step in list(report.get("steps") or []):
            label = "PASS" if step.get("ok") else "FAIL"
            detail = step.get("detail")
            if detail:
                print(f"- {step.get('step')}: {label} ({detail})")
            else:
                print(f"- {step.get('step')}: {label}")

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
        res = _doctor(audio=getattr(args, "audio", None))
        status = "OK" if res.ok else "MISSING_DEPS"
        print(f"claw-daw doctor: {status}")
        for n in res.notes:
            print(f"- {n}")
        if not res.ok:
            print("\nLinux (Debian/Ubuntu): sudo apt-get install fluidsynth ffmpeg fluid-soundfont-gm")
            print("macOS: brew install fluidsynth ffmpeg")
            print("Windows (PowerShell): iwr https://sdiaoune.github.io/claw-daw/install_win.ps1 -useb | iex")
        return

    if args.cmd == "paths":
        if args.soundfont:
            for pth in default_soundfont_paths():
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

    if args.cmd == "arrange-spec":
        from claw_daw.arrange.arrange_spec import load_arrange_spec
        from claw_daw.arrange.compiler import compile_arrangement
        from claw_daw.io.project_json import load_project, save_project

        spec = load_arrange_spec(args.spec)
        proj = load_project(args.inp)
        compile_arrangement(proj, spec, clear_existing=not bool(args.keep_existing_clips))
        save_project(proj, args.out)
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

        out_prefix = _normalize_out_prefix(str(args.out_prefix))

        if args.prompt_file:
            prompt_text = Path(args.prompt_file).read_text(encoding="utf-8")
        else:
            prompt_text = args.prompt or ""

        if not prompt_text.strip():
            raise SystemExit("ERROR: provide --prompt or --prompt-file")

        res = generate_from_prompt(
            prompt_text,
            out_prefix=out_prefix,
            max_iters=int(args.iters),
            seed=int(args.seed),
            max_similarity=float(args.max_similarity),
            soundfont=None,
            render=False,
            preview_bars=int(args.preview_bars),
        )

        print(f"wrote: {res.script_path}")
        if res.similarities:
            print("similarities:")
            for i, s in enumerate(res.similarities, start=1):
                print(f"- iter{i}: {s:.3f}")
        if args.render:
            from claw_daw.cli.headless import HeadlessRunner
            from claw_daw.quality_workflow import QualityWorkflowError, run_quality_workflow

            script_lines = Path(res.script_path).read_text(encoding="utf-8").splitlines()
            runnable: list[str] = []
            has_save = False
            for ln in script_lines:
                s = ln.strip()
                if s.startswith("export_"):
                    continue
                if s.startswith("save_project "):
                    has_save = True
                runnable.append(ln)
            if not has_save:
                runnable.append(f"save_project out/{out_prefix}.json")

            r = HeadlessRunner(soundfont=None, strict=True, dry_run=False)
            r.run_lines(runnable, base_dir=Path(res.script_path).parent)

            from claw_daw.io.project_json import load_project

            proj = load_project(f"out/{out_prefix}.json")
            preview_trim = max(8.0, (60.0 / max(1.0, float(proj.tempo_bpm))) * 4.0 * float(args.preview_bars))

            try:
                quality = run_quality_workflow(
                    project_json=f"out/{out_prefix}.json",
                    out_prefix=out_prefix,
                    soundfont=str(args.soundfont) if getattr(args, "soundfont", None) else None,
                    preset=str(args.quality_preset),
                    presets_path=str(args.quality_presets),
                    section_gain=bool(args.section_gain),
                    preview_trim=float(preview_trim),
                )
            except QualityWorkflowError as e:
                _print_quality_report(e.report)
                raise SystemExit(f"ERROR: {e}") from e

            _print_quality_report(quality)
        return

    if args.cmd == "pack":
        from claw_daw.genre_packs.pipeline import generate_from_genre_pack
        from claw_daw.genre_packs.v1 import list_packs_v1

        out_prefix = _normalize_out_prefix(str(args.out_prefix))

        try:
            res = generate_from_genre_pack(
                str(args.pack),
                out_prefix=out_prefix,
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
        if args.render:
            from claw_daw.cli.headless import HeadlessRunner
            from claw_daw.quality_workflow import QualityWorkflowError, run_quality_workflow

            script_lines = Path(res.script_path).read_text(encoding="utf-8").splitlines()
            runnable: list[str] = []
            has_save = False
            for ln in script_lines:
                s = ln.strip()
                if s.startswith("export_"):
                    continue
                if s.startswith("save_project "):
                    has_save = True
                runnable.append(ln)
            if not has_save:
                runnable.append(f"save_project out/{out_prefix}.json")

            r = HeadlessRunner(soundfont=None, strict=True, dry_run=False)
            r.run_lines(runnable, base_dir=Path(res.script_path).parent)

            try:
                quality = run_quality_workflow(
                    project_json=f"out/{out_prefix}.json",
                    out_prefix=out_prefix,
                    soundfont=str(args.soundfont) if getattr(args, "soundfont", None) else None,
                    preset=str(args.quality_preset),
                    presets_path=str(args.quality_presets),
                    section_gain=bool(args.section_gain),
                )
            except QualityWorkflowError as e:
                _print_quality_report(e.report)
                raise SystemExit(f"ERROR: {e}") from e

            _print_quality_report(quality)
        return

    if args.cmd == "stylepack":
        from claw_daw.stylepacks.run import run_stylepack
        from claw_daw.stylepacks.types import BeatSpec

        out_prefix = _normalize_out_prefix(str(args.out_prefix))

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
            name=out_prefix,
            stylepack=str(args.stylepack),  # type: ignore[arg-type]
            seed=int(args.seed),
            max_attempts=int(args.attempts),
            length_bars=int(args.bars),
            knobs=knobs,
            score_threshold=float(args.score_threshold),
            max_similarity=float(args.max_similarity),
        )

        rep = run_stylepack(
            spec,
            out_prefix=out_prefix,
            soundfont=str(args.soundfont),
            quality_preset=str(args.quality_preset),
            quality_presets_path=str(args.quality_presets),
            section_gain=bool(args.section_gain),
        )
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

    if args.cmd == "quality":
        from claw_daw.quality_workflow import QualityWorkflowError, run_quality_workflow

        try:
            report = run_quality_workflow(
                project_json=str(args.project_json),
                out_prefix=str(args.out_prefix),
                soundfont=str(args.soundfont) if getattr(args, "soundfont", None) else None,
                preset=str(args.preset),
                presets_path=str(args.presets),
                mix_out=str(args.mix_out) if getattr(args, "mix_out", None) else None,
                section_gain=bool(args.section_gain),
                preview_trim=float(args.preview_trim),
                lufs_guidance=not bool(args.no_lufs_guidance),
            )
        except QualityWorkflowError as e:
            _print_quality_report(e.report)
            raise SystemExit(f"ERROR: {e}") from e
        _print_quality_report(report)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
