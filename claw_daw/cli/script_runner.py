from __future__ import annotations

import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

from claw_daw.arrange.types import Clip, Pattern
from claw_daw.io.midi import export_midi
from claw_daw.model.types import Note, Project, Track
from claw_daw.util.drumkit import get_drum_kit


PPQ_DEFAULT = 480


def _ticks_per_bar(ppq: int) -> int:
    return ppq * 4


def _parse_int(x: str) -> int:
    return int(x.strip())


def _parse_kv(tokens: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for t in tokens:
        if "=" not in t:
            continue
        k, v = t.split("=", 1)
        out[k.strip()] = v.strip().strip('"')
    return out


def _sanitize_filename(s: str) -> str:
    s = s.strip().lower().replace(" ", "_")
    s = re.sub(r"[^a-z0-9._-]+", "_", s)
    s = re.sub(r"_+", "_", s)
    return s or "untitled"


@dataclass
class RenderOptions:
    soundfont: Path
    out_dir: Path = Path("out")


class ScriptState:
    def __init__(self) -> None:
        self.project: Project | None = None

    def require_project(self) -> Project:
        if not self.project:
            raise RuntimeError("No project. Use new_project first.")
        return self.project


def run_script(
    lines: list[str], *, base_dir: Path | None = None, default_soundfont: Path | None = None
) -> Project:
    st = ScriptState()

    repo_root = Path.cwd()

    def resolve_path(p: str) -> Path:
        path = Path(p.strip().strip('"')).expanduser()
        if path.is_absolute():
            return path

        # Convention: anything under out/ should be relative to repo root, not script dir.
        parts = path.parts
        if parts and parts[0] == "out":
            return (repo_root / path).resolve()

        if base_dir is not None:
            return (base_dir / path).resolve()

        return path.resolve()

    for lineno, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        # include other scripts
        if line.startswith("include "):
            inc = line.split(" ", 1)[1].strip()
            inc_path = resolve_path(inc)
            inc_lines = inc_path.read_text(encoding="utf-8").splitlines()
            run_script(inc_lines, base_dir=inc_path.parent)
            continue

        parts = shlex.split(line)
        cmd, args = parts[0], parts[1:]

        if cmd == "new_project":
            name = args[0]
            tempo = _parse_int(args[1])
            st.project = Project(name=name, tempo_bpm=tempo, ppq=PPQ_DEFAULT)
            continue

        if cmd == "set_swing":
            st.require_project().swing_percent = _parse_int(args[0])
            continue

        if cmd == "add_track":
            p = st.require_project()
            name = args[0]
            program = _parse_int(args[1])
            ch = p.next_free_channel() if name.lower() != "drums" else 9
            t = Track(name=name, channel=ch, program=program)
            p.tracks.append(t)
            continue

        if cmd == "set_sampler":
            p = st.require_project()
            tidx = _parse_int(args[0])
            sampler = args[1]
            p.tracks[tidx].sampler = sampler
            continue

        if cmd == "set_drum_kit":
            p = st.require_project()
            tidx = _parse_int(args[0])
            kit = args[1]
            p.tracks[tidx].drum_kit = get_drum_kit(kit).name
            continue

        if cmd == "set_volume":
            p = st.require_project()
            tidx = _parse_int(args[0])
            p.tracks[tidx].volume = _parse_int(args[1])
            continue

        if cmd == "set_pan":
            p = st.require_project()
            tidx = _parse_int(args[0])
            p.tracks[tidx].pan = _parse_int(args[1])
            continue

        if cmd == "set_reverb":
            p = st.require_project()
            tidx = _parse_int(args[0])
            p.tracks[tidx].reverb = _parse_int(args[1])
            continue

        if cmd == "new_pattern":
            p = st.require_project()
            tidx = _parse_int(args[0])
            pat_name = args[1]
            length = _parse_int(args[2])
            p.tracks[tidx].patterns[pat_name] = Pattern(name=pat_name, length=length)
            continue

        if cmd == "add_note_pat":
            p = st.require_project()
            tidx = _parse_int(args[0])
            pat_name = args[1]

            role: str | None = None
            pitch = 0
            try:
                pitch = _parse_int(args[2])
            except Exception:
                role = str(args[2]).strip()

            start = _parse_int(args[3])
            dur = _parse_int(args[4])
            vel = _parse_int(args[5])
            pat = p.tracks[tidx].patterns[pat_name]
            pat.notes.append(Note(start=start, duration=dur, pitch=pitch, velocity=vel, role=role))
            continue

        if cmd == "place_pattern":
            p = st.require_project()
            tidx = _parse_int(args[0])
            pat_name = args[1]
            start = _parse_int(args[2])
            repeats = _parse_int(args[3])
            p.tracks[tidx].clips.append(Clip(pattern=pat_name, start=start, repeats=repeats))
            continue

        if cmd == "export_project":
            p = st.require_project()
            out = resolve_path(args[0])
            out.parent.mkdir(parents=True, exist_ok=True)
            import json

            out.write_text(json.dumps(p.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
            continue

        if cmd == "export_midi":
            p = st.require_project()
            out = resolve_path(args[0])
            export_midi(p, out)
            continue

        if cmd in ("export_wav", "export_mp3"):
            # We render via FluidSynth from a temporary MIDI.
            p = st.require_project()
            out = resolve_path(args[0])
            kv = _parse_kv(args[1:])
            trim = int(kv.get("trim", "0")) if kv.get("trim") else 0
            preset = kv.get("preset", "")

            tmp_dir = out.parent
            tmp_dir.mkdir(parents=True, exist_ok=True)
            tmp_midi = tmp_dir / f".{_sanitize_filename(out.stem)}.tmp.mid"
            tmp_wav = tmp_dir / f".{_sanitize_filename(out.stem)}.tmp.wav"
            export_midi(p, tmp_midi)

            # FluidSynth render
            sf2 = kv.get("soundfont")
            if sf2:
                sf2_path = resolve_path(sf2)
            elif default_soundfont is not None:
                sf2_path = default_soundfont
            else:
                raise RuntimeError(
                    "export_wav/export_mp3 requires soundfont=... or provide --soundfont when running --headless"
                )

            subprocess.check_call([
                "fluidsynth",
                "-ni",
                str(sf2_path),
                str(tmp_midi),
                "-F",
                str(tmp_wav),
                "-r",
                "44100",
            ])

            # Post-process
            ff_args = ["ffmpeg", "-y", "-i", str(tmp_wav)]
            if trim > 0:
                ff_args += ["-t", str(trim)]

            # A lightweight "clean" preset: mild loudness normalization.
            if preset == "clean":
                ff_args += ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11"]

            if cmd == "export_wav":
                ff_args += [str(out)]
            else:
                ff_args += ["-codec:a", "libmp3lame", "-q:a", "2", str(out)]

            subprocess.check_call(ff_args)
            tmp_midi.unlink(missing_ok=True)
            tmp_wav.unlink(missing_ok=True)
            continue

        raise ValueError(f"Line {lineno}: unknown command '{cmd}'")

    return st.require_project()


def read_lines(path: str) -> list[str]:
    return Path(path).read_text(encoding="utf-8").splitlines()


def render_from_script(*, script_path: str, soundfont: str) -> None:
    script = Path(script_path).expanduser().resolve()
    base = script.parent
    lines = read_lines(str(script))
    proj = run_script(lines, base_dir=base)

    # Post-run convenience: if the script didn't export, we at least save project json.
    # (Most scripts should explicitly export.)
    _ = proj
