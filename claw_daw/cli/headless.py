from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from random import Random

from claw_daw.arrange.sections import Section, Variation
from claw_daw.arrange.transform import reverse as pat_reverse
from claw_daw.arrange.transform import shift as pat_shift
from claw_daw.arrange.transform import stretch as pat_stretch
from claw_daw.arrange.transform import transpose as pat_transpose
from claw_daw.arrange.transform import velocity_scale as pat_vel
from claw_daw.arrange.types import Clip, Pattern
from claw_daw.audio.encode import encode_audio
from claw_daw.audio.mastering import MASTER_PRESETS, master_wav
from claw_daw.audio.render import render_project_wav
from claw_daw.audio.spectrogram import SpectrogramOptions, band_energy_report, render_spectrogram_png
from claw_daw.audio.stems import export_stems
from claw_daw.io.midi import export_midi
from claw_daw.io.project_json import load_project, save_project
from claw_daw.model.types import Note, Project, Track
from claw_daw.util.derived import bars_estimate, project_song_end_tick, song_length_seconds
from claw_daw.util.gm import parse_program
from claw_daw.util.limits import (
    MAX_CLIPS_PER_TRACK,
    MAX_NOTES_PER_PATTERN,
    MAX_NOTES_PER_TRACK,
    MAX_PATTERNS_PER_TRACK,
    MAX_TRACKS,
)
from claw_daw.util.quantize import parse_grid, quantize_project_track
from claw_daw.util.region import slice_project_range
from claw_daw.util.timecode import parse_timecode_ticks
from claw_daw.util.reference import analyze_references
from claw_daw.util.validate import validate_and_migrate_project


@dataclass
class HeadlessContext:
    project: Project | None = None
    soundfont: str | None = None


def _sanitize_filename(s: str) -> str:
    s = s.strip().lower().replace(" ", "_")
    s = re.sub(r"[^a-z0-9._-]+", "_", s)
    s = re.sub(r"_+", "_", s)
    return s or "untitled"


def _default_export_path(project: Project, ext: str, *, out_dir: str = "out") -> str:
    name = _sanitize_filename(project.name)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    return str(Path(out_dir) / f"{name}.{ext}")


def _ticks_per_bar(project: Project) -> int:
    return int(project.ppq) * 4


def _tick(proj: Project, s: str) -> int:
    return parse_timecode_ticks(proj, s)


class HeadlessRunner:
    def __init__(self, *, soundfont: str | None = None, strict: bool = False, dry_run: bool = False) -> None:
        self.ctx = HeadlessContext(soundfont=soundfont)
        self.strict = strict
        self.dry_run = dry_run
        self.commands_executed = 0
        self.warnings: list[str] = []

    def run_lines(self, lines: list[str], *, base_dir: Path | None = None) -> None:
        base = base_dir
        for lineno, raw in enumerate(lines, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            # include other scripts
            if line.startswith("include "):
                inc = line.split(" ", 1)[1].strip().strip('"')
                inc_path = Path(inc)
                if base is not None and not inc_path.is_absolute():
                    inc_path = base / inc_path
                if not inc_path.exists():
                    msg = f"include not found: {inc_path}"
                    if self.strict:
                        raise FileNotFoundError(msg)
                    self.warnings.append(msg)
                    continue
                inc_lines = inc_path.read_text(encoding="utf-8").splitlines()
                self.run_lines(inc_lines, base_dir=inc_path.parent)
                continue

            try:
                self.run_command(line)
                self.commands_executed += 1
            except Exception as e:
                msg = f"Headless error line {lineno}: {line} ({e})"
                if self.strict:
                    raise RuntimeError(msg) from e
                self.warnings.append(msg)
                continue

    def run_command(self, line: str) -> None:
        parts = line.split()
        cmd, *args = parts

        if cmd == "new_project":
            name = args[0]
            bpm = int(args[1]) if len(args) > 1 else 120
            self.ctx.project = Project(name=name, tempo_bpm=bpm)
            self.ctx.project.dirty = True
            return

        if cmd in {"template_house", "template_lofi", "template_hiphop"}:
            # template_house <out_prefix>
            style = cmd.split("_", 1)[1]
            out_prefix = args[0] if args else f"out_template_{style}"
            self.run_command(f"render_demo {style} {out_prefix}")
            return

        if cmd == "render_demo":
            # render_demo <style> <out_prefix>
            style = args[0]
            out_prefix = args[1]
            from claw_daw.cli.demo import demo_script_text

            script = demo_script_text(style)
            rewritten: list[str] = []
            for ln in script.splitlines():
                if ln.strip().startswith("export_mp3 "):
                    rewritten.append(f"export_mp3 {out_prefix}.mp3 trim=60 preset=demo fade=0.15")
                elif ln.strip().startswith("export_midi "):
                    rewritten.append(f"export_midi {out_prefix}.mid")
                elif ln.strip().startswith("save_project "):
                    rewritten.append(f"save_project {out_prefix}.json")
                else:
                    rewritten.append(ln)
            self.run_lines(rewritten, base_dir=Path.cwd())

            # shareability: a deterministic cover text file.
            cover = Path(f"{out_prefix}_cover.txt")
            proj = self.require_project()
            end_tick = project_song_end_tick(proj)
            cover.write_text(
                "\n".join(
                    [
                        "claw-daw demo",
                        f"style: {style}",
                        f"project: {proj.name}",
                        f"tempo_bpm: {proj.tempo_bpm}",
                        f"ppq: {proj.ppq}",
                        f"swing_percent: {proj.swing_percent}",
                        f"song_length_ticks: {end_tick}",
                        f"song_length_seconds_est: {song_length_seconds(proj, end_tick):.2f}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            return

        # Commands that don't require an existing project
        if cmd == "open_project":
            self.ctx.project = load_project(args[0])
            return

        proj = self.require_project()

        if cmd == "save_project":
            save_project(proj, args[0] if args else None)
            return

        if cmd == "add_track":
            if len(proj.tracks) >= MAX_TRACKS:
                raise RuntimeError(f"max tracks reached ({MAX_TRACKS})")
            # add_track <name> [program]
            name = args[0]
            program = parse_program(args[1]) if len(args) > 1 else 0
            ch = proj.next_free_channel()
            proj.tracks.append(Track(name=name, channel=ch, program=program))
            proj.dirty = True
            return

        if cmd == "delete_track":
            idx = int(args[0]) if args else len(proj.tracks) - 1
            if idx < 0 or idx >= len(proj.tracks):
                raise IndexError("track index out of range")
            proj.tracks.pop(idx)
            proj.dirty = True
            return

        if cmd == "set_program":
            idx = int(args[0])
            proj.tracks[idx].program = parse_program(args[1])
            proj.dirty = True
            return
        if cmd == "set_volume":
            idx = int(args[0])
            proj.tracks[idx].volume = max(0, min(127, int(args[1])))
            proj.dirty = True
            return
        if cmd == "set_pan":
            idx = int(args[0])
            proj.tracks[idx].pan = max(0, min(127, int(args[1])))
            proj.dirty = True
            return
        if cmd == "set_reverb":
            idx = int(args[0])
            proj.tracks[idx].reverb = max(0, min(127, int(args[1])))
            proj.dirty = True
            return
        if cmd == "set_chorus":
            idx = int(args[0])
            proj.tracks[idx].chorus = max(0, min(127, int(args[1])))
            proj.dirty = True
            return

        if cmd == "set_sampler":
            # set_sampler <track_index> <drums|808|none>
            idx = int(args[0])
            mode = (args[1] if len(args) > 1 else "none").strip().lower()
            if mode in {"none", "off", "0"}:
                proj.tracks[idx].sampler = None
            elif mode in {"drums", "808"}:
                proj.tracks[idx].sampler = mode
            else:
                raise ValueError("sampler mode must be: drums, 808, none")
            proj.dirty = True
            return

        if cmd == "set_glide":
            # set_glide <track_index> <ticks|bar:beat>
            idx = int(args[0])
            proj.tracks[idx].glide_ticks = max(0, _tick(proj, args[1]))
            proj.dirty = True
            return

        if cmd == "set_humanize":
            # set_humanize <track_index> timing=<ticks> velocity=<0-30> seed=<int>
            idx = int(args[0])
            t = proj.tracks[idx]
            for a in args[1:]:
                if a.startswith("timing="):
                    t.humanize_timing = max(0, int(a.split("=", 1)[1]))
                if a.startswith("velocity="):
                    t.humanize_velocity = max(0, int(a.split("=", 1)[1]))
                if a.startswith("seed="):
                    t.humanize_seed = int(a.split("=", 1)[1])
            proj.dirty = True
            return

        if cmd == "set_swing":
            proj.swing_percent = max(0, min(75, int(args[0])))
            proj.dirty = True
            return

        if cmd == "set_loop":
            proj.loop_start = _tick(proj, args[0])
            proj.loop_end = _tick(proj, args[1])
            proj.dirty = True
            return
        if cmd == "clear_loop":
            proj.loop_start = None
            proj.loop_end = None
            proj.dirty = True
            return

        if cmd == "set_render_region":
            proj.render_start = _tick(proj, args[0])
            proj.render_end = _tick(proj, args[1])
            proj.dirty = True
            return
        if cmd == "clear_render_region":
            proj.render_start = None
            proj.render_end = None
            proj.dirty = True
            return

        if cmd == "insert_note":
            # legacy: insert_note <track> <pitch> <start> <dur> [vel]
            ti = int(args[0])
            if len(proj.tracks[ti].notes) >= MAX_NOTES_PER_TRACK:
                raise RuntimeError(f"max notes reached ({MAX_NOTES_PER_TRACK})")
            pitch = int(args[1])
            start = _tick(proj, args[2])
            dur = _tick(proj, args[3])
            vel = int(args[4]) if len(args) > 4 else 100
            proj.tracks[ti].notes.append(Note(start=start, duration=dur, pitch=pitch, velocity=vel))
            proj.dirty = True
            return

        # -------- arrangement ops --------

        if cmd == "new_pattern":
            ti = int(args[0])
            if len(proj.tracks[ti].patterns) >= MAX_PATTERNS_PER_TRACK:
                raise RuntimeError(f"max patterns reached ({MAX_PATTERNS_PER_TRACK})")
            name = args[1]
            length = _tick(proj, args[2])
            proj.tracks[ti].patterns[name] = Pattern(name=name, length=length)
            proj.dirty = True
            return

        if cmd == "rename_pattern":
            ti = int(args[0])
            old, new = args[1], args[2]
            t = proj.tracks[ti]
            if old not in t.patterns:
                raise KeyError(f"pattern not found: {old}")
            if new in t.patterns:
                raise KeyError(f"pattern already exists: {new}")
            pat = t.patterns.pop(old)
            pat.name = new
            t.patterns[new] = pat
            # update clip refs
            for c in t.clips:
                if c.pattern == old:
                    c.pattern = new
            proj.dirty = True
            return

        if cmd == "delete_pattern":
            ti = int(args[0])
            name = args[1]
            t = proj.tracks[ti]
            t.patterns.pop(name)
            # also delete clips that referenced it
            t.clips = [c for c in t.clips if c.pattern != name]
            proj.dirty = True
            return

        if cmd == "duplicate_pattern":
            ti = int(args[0])
            src, dst = args[1], args[2]
            t = proj.tracks[ti]
            if dst in t.patterns:
                raise KeyError(f"pattern already exists: {dst}")
            if len(t.patterns) >= MAX_PATTERNS_PER_TRACK:
                raise RuntimeError(f"max patterns reached ({MAX_PATTERNS_PER_TRACK})")
            psrc = t.patterns[src]
            pdst = Pattern(name=dst, length=psrc.length)
            pdst.notes = [Note(start=n.start, duration=n.duration, pitch=n.pitch, velocity=n.velocity) for n in psrc.notes]
            t.patterns[dst] = pdst
            proj.dirty = True
            return

        if cmd == "pattern_transpose":
            # pattern_transpose <track> <pattern> <semitones>
            ti = int(args[0])
            name = args[1]
            semi = int(args[2])
            t = proj.tracks[ti]
            t.patterns[name] = pat_transpose(t.patterns[name], semi)
            proj.dirty = True
            return

        if cmd == "pattern_shift":
            # pattern_shift <track> <pattern> <ticks>
            ti = int(args[0])
            name = args[1]
            ticks = _tick(proj, args[2])
            t = proj.tracks[ti]
            t.patterns[name] = pat_shift(t.patterns[name], ticks)
            proj.dirty = True
            return

        if cmd == "pattern_stretch":
            # pattern_stretch <track> <pattern> <factor>
            ti = int(args[0])
            name = args[1]
            factor = float(args[2])
            t = proj.tracks[ti]
            t.patterns[name] = pat_stretch(t.patterns[name], factor)
            proj.dirty = True
            return

        if cmd == "pattern_reverse":
            # pattern_reverse <track> <pattern>
            ti = int(args[0])
            name = args[1]
            t = proj.tracks[ti]
            t.patterns[name] = pat_reverse(t.patterns[name])
            proj.dirty = True
            return

        if cmd == "pattern_vel":
            # pattern_vel <track> <pattern> <scale>
            ti = int(args[0])
            name = args[1]
            scale = float(args[2])
            t = proj.tracks[ti]
            t.patterns[name] = pat_vel(t.patterns[name], scale)
            proj.dirty = True
            return

        if cmd == "add_note_pat":
            ti = int(args[0])
            pat = proj.tracks[ti].patterns[args[1]]
            if len(pat.notes) >= MAX_NOTES_PER_PATTERN:
                raise RuntimeError(f"max notes/pattern reached ({MAX_NOTES_PER_PATTERN})")
            pitch = int(args[2])
            start = _tick(proj, args[3])
            dur = _tick(proj, args[4])
            vel = int(args[5]) if len(args) > 5 else 100
            pat.notes.append(Note(start=start, duration=dur, pitch=pitch, velocity=vel))
            proj.dirty = True
            return

        if cmd == "place_pattern":
            ti = int(args[0])
            t = proj.tracks[ti]
            if len(t.clips) >= MAX_CLIPS_PER_TRACK:
                raise RuntimeError(f"max clips reached ({MAX_CLIPS_PER_TRACK})")
            name = args[1]
            start = _tick(proj, args[2])
            reps = int(args[3]) if len(args) > 3 else 1
            t.clips.append(Clip(pattern=name, start=start, repeats=reps))
            proj.dirty = True
            return

        if cmd == "move_clip":
            # move_clip <track> <clip_index> <new_start>
            ti = int(args[0])
            ci = int(args[1])
            proj.tracks[ti].clips[ci].start = _tick(proj, args[2])
            proj.dirty = True
            return

        if cmd == "delete_clip":
            # delete_clip <track> <clip_index>
            ti = int(args[0])
            ci = int(args[1])
            proj.tracks[ti].clips.pop(ci)
            proj.dirty = True
            return

        if cmd == "copy_bars":
            # copy_bars <track> <src_bar> <bars> <dst_bar>
            ti = int(args[0])
            src_bar = int(args[1])
            bars = int(args[2])
            dst_bar = int(args[3])
            t = proj.tracks[ti]
            tpbar = _ticks_per_bar(proj)
            src_start = src_bar * tpbar
            src_end = src_start + bars * tpbar
            dst_start = dst_bar * tpbar
            delta = dst_start - src_start

            to_copy = [c for c in t.clips if src_start <= c.start < src_end]
            if len(t.clips) + len(to_copy) > MAX_CLIPS_PER_TRACK:
                raise RuntimeError(f"would exceed max clips ({MAX_CLIPS_PER_TRACK})")
            for c in to_copy:
                t.clips.append(Clip(pattern=c.pattern, start=c.start + delta, repeats=c.repeats))
            proj.dirty = True
            return

        if cmd == "clear_clips":
            ti = int(args[0])
            proj.tracks[ti].clips = []
            proj.dirty = True
            return

        if cmd == "add_section":
            # add_section <name> <start> <length>
            name = args[0]
            start = _tick(proj, args[1])
            length = _tick(proj, args[2])
            proj.sections.append(Section(name=name, start=start, length=length))
            proj.dirty = True
            return

        if cmd == "add_variation":
            # add_variation <section_name> <track_index> <src_pattern> <dst_pattern>
            sec = args[0]
            ti = int(args[1])
            proj.variations.append(Variation(section=sec, track_index=ti, src_pattern=args[2], dst_pattern=args[3]))
            proj.dirty = True
            return

        # -------- generators --------

        if cmd == "gen_drums":
            # gen_drums <track> <pattern> <length_ticks> <style> [seed=0] [density=0.8]
            ti = int(args[0])
            name = args[1]
            length = _tick(proj, args[2])
            style = args[3].lower()
            seed = 0
            density = 0.8
            for a in args[4:]:
                if a.startswith("seed="):
                    seed = int(a.split("=", 1)[1])
                if a.startswith("density="):
                    density = float(a.split("=", 1)[1])

            rnd = Random(seed)
            t = proj.tracks[ti]
            if name not in t.patterns:
                if len(t.patterns) >= MAX_PATTERNS_PER_TRACK:
                    raise RuntimeError(f"max patterns reached ({MAX_PATTERNS_PER_TRACK})")
                t.patterns[name] = Pattern(name=name, length=length)
            pat = t.patterns[name]
            pat.length = length
            pat.notes = []

            step = proj.ppq // 4  # 16th
            steps = max(1, length // step)

            kick = 36
            snare = 38
            hat = 42

            for s in range(steps):
                tick = s * step
                # hats: steady with dropouts
                if style in {"house", "lofi", "hiphop"}:
                    if rnd.random() < max(0.2, min(1.0, density)):
                        pat.notes.append(Note(start=tick, duration=step // 2, pitch=hat, velocity=65))

                # kick patterns
                if style == "house":
                    if s % 4 == 0:
                        pat.notes.append(Note(start=tick, duration=step, pitch=kick, velocity=110))
                elif style == "hiphop":
                    if s in {0, 6, 8, 14} and rnd.random() < density:
                        pat.notes.append(Note(start=tick, duration=step, pitch=kick, velocity=115))
                else:  # lofi
                    if s in {0, 7, 10, 14} and rnd.random() < density:
                        pat.notes.append(Note(start=tick, duration=step, pitch=kick, velocity=100))

                # snare on 2 and 4
                if s % 8 == 4:
                    pat.notes.append(Note(start=tick, duration=step, pitch=snare, velocity=105))

            proj.dirty = True
            return

        # -------- editing/util --------

        if cmd == "quantize_track":
            ti = int(args[0])
            grid = parse_grid(proj.ppq, args[1])
            strength = float(args[2]) if len(args) > 2 else 1.0
            quantize_project_track(proj, ti, grid, strength)
            return

        # -------- export --------

        if cmd == "export_midi":
            if self.dry_run:
                return
            export_midi(proj, args[0])
            return

        if cmd == "export_wav":
            # export_wav [path] [preset=demo] [fade=0.15] [sr=44100] [trim=60]
            if self.dry_run:
                return
            sf = self.ctx.soundfont
            if not sf:
                raise RuntimeError("soundfont not set for headless export_wav")

            out_wav = args[0] if args and not args[0].startswith("preset=") else _default_export_path(proj, "wav")
            preset = "demo"
            fade = 0.0
            sr = 44100
            trim = None
            for a in args[1:] if out_wav == args[0] else args:
                if a.startswith("preset="):
                    preset = a.split("=", 1)[1]
                if a.startswith("fade="):
                    fade = float(a.split("=", 1)[1])
                if a.startswith("sr="):
                    sr = int(a.split("=", 1)[1])
                if a.startswith("trim="):
                    trim = float(a.split("=", 1)[1])

            if preset not in MASTER_PRESETS:
                raise ValueError(f"preset must be one of: {', '.join(sorted(MASTER_PRESETS))}")

            # derive region
            start = proj.render_start if proj.render_start is not None else 0
            end = proj.render_end if proj.render_end is not None else project_song_end_tick(proj)
            if proj.loop_start is not None and proj.loop_end is not None:
                start, end = proj.loop_start, proj.loop_end
            render_proj = slice_project_range(proj, start, end)

            render_project_wav(render_proj, soundfont=sf, out_wav=out_wav, sample_rate=sr)

            # mastering + fades
            norm = Path(out_wav).with_suffix(".master.wav")
            mastered = master_wav(out_wav, str(norm), sample_rate=sr, trim_seconds=trim, preset=preset, fade_in_seconds=fade, fade_out_seconds=fade)
            if mastered != out_wav:
                Path(out_wav).unlink(missing_ok=True)
                Path(mastered).rename(out_wav)
            return

        if cmd == "export_mp3":
            # export_mp3 [out.mp3] [trim=60] [sr=44100] [br=192k] [preset=demo] [fade=0.15]
            if self.dry_run:
                return
            sf = self.ctx.soundfont
            if not sf:
                raise RuntimeError("soundfont not set")

            out_mp3 = args[0] if args and args[0].endswith(".mp3") else _default_export_path(proj, "mp3")
            sr = 44100
            trim = None
            br = "192k"
            preset = "demo"
            fade = 0.0
            rest = args[1:] if out_mp3 == args[0] else args
            for a in rest:
                if a.startswith("sr="):
                    sr = int(a.split("=", 1)[1])
                if a.startswith("trim="):
                    trim = float(a.split("=", 1)[1])
                if a.startswith("br="):
                    br = a.split("=", 1)[1]
                if a.startswith("preset="):
                    preset = a.split("=", 1)[1]
                if a.startswith("fade="):
                    fade = float(a.split("=", 1)[1])

            tmp_wav = Path(out_mp3).with_suffix(".tmp.wav")
            self.run_command(
                f"export_wav {tmp_wav} preset={preset} fade={fade} sr={sr}" + (f" trim={trim}" if trim else "")
            )
            encode_audio(str(tmp_wav), out_mp3, trim_seconds=None, sample_rate=sr, codec="mp3", bitrate=br)
            tmp_wav.unlink(missing_ok=True)
            return

        if cmd == "export_m4a":
            # export_m4a [out.m4a] [trim=60] [sr=44100] [br=192k] [preset=demo] [fade=0.15]
            if self.dry_run:
                return
            sf = self.ctx.soundfont
            if not sf:
                raise RuntimeError("soundfont not set")

            out_m4a = args[0] if args and args[0].endswith(".m4a") else _default_export_path(proj, "m4a")
            sr = 44100
            trim = None
            br = "192k"
            preset = "demo"
            fade = 0.0
            rest = args[1:] if out_m4a == args[0] else args
            for a in rest:
                if a.startswith("sr="):
                    sr = int(a.split("=", 1)[1])
                if a.startswith("trim="):
                    trim = float(a.split("=", 1)[1])
                if a.startswith("br="):
                    br = a.split("=", 1)[1]
                if a.startswith("preset="):
                    preset = a.split("=", 1)[1]
                if a.startswith("fade="):
                    fade = float(a.split("=", 1)[1])

            tmp_wav = Path(out_m4a).with_suffix(".tmp.wav")
            self.run_command(
                f"export_wav {tmp_wav} preset={preset} fade={fade} sr={sr}" + (f" trim={trim}" if trim else "")
            )
            encode_audio(str(tmp_wav), out_m4a, trim_seconds=None, sample_rate=sr, codec="m4a", bitrate=br)
            tmp_wav.unlink(missing_ok=True)
            return

        if cmd == "export_stems":
            sf = self.ctx.soundfont
            if not sf:
                raise RuntimeError("soundfont not set for headless export_stems")
            export_stems(proj, soundfont=sf, out_dir=args[0])
            return

        if cmd == "spectrogram_audio":
            # spectrogram_audio <in_audio> <out.png> [sr=44100] [size=1200x600] [legend=1] [color=fiery] [scale=log] [gain=5]
            if self.dry_run:
                return
            inp = args[0]
            out_png = args[1]
            sr = 44100
            size = "1200x600"
            legend = True
            color = "fiery"
            scale = "log"
            gain = 5.0
            for a in args[2:]:
                if a.startswith("sr="):
                    sr = int(a.split("=", 1)[1])
                if a.startswith("size="):
                    size = a.split("=", 1)[1]
                if a.startswith("legend="):
                    legend = a.split("=", 1)[1] not in {"0", "false", "no"}
                if a.startswith("color="):
                    color = a.split("=", 1)[1]
                if a.startswith("scale="):
                    scale = a.split("=", 1)[1]
                if a.startswith("gain="):
                    gain = float(a.split("=", 1)[1])

            render_spectrogram_png(inp, out_png, sample_rate=sr, opts=SpectrogramOptions(size=size, legend=legend, color=color, scale=scale, gain=gain))
            # also emit a tiny band report next to the png
            rep = band_energy_report(inp)
            Path(out_png).with_suffix(".bands.txt").write_text(
                "\n".join(
                    [
                        f"spectrogram_audio: {inp}",
                        f"full.mean_db={rep['full']['mean_volume']:.1f} full.max_db={rep['full']['max_volume']:.1f}",
                        f"sub<90.mean_db={rep['sub_lt90']['mean_volume']:.1f} sub<90.max_db={rep['sub_lt90']['max_volume']:.1f}",
                        f"rest>=90.mean_db={rep['rest_ge90']['mean_volume']:.1f} rest>=90.max_db={rep['rest_ge90']['max_volume']:.1f}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            return

        if cmd == "export_spectrogram":
            # export_spectrogram [out.png] [sr=44100] [size=1200x600] [legend=1] [color=fiery] [scale=log] [gain=5]
            if self.dry_run:
                return
            sf = self.ctx.soundfont
            if not sf:
                raise RuntimeError("soundfont not set for export_spectrogram")

            out_png = args[0] if args and args[0].endswith(".png") else _default_export_path(proj, "spectrogram.png")
            sr = 44100
            size = "1200x600"
            legend = True
            color = "fiery"
            scale = "log"
            gain = 5.0
            rest = args[1:] if args and args[0] == out_png else args
            for a in rest:
                if a.startswith("sr="):
                    sr = int(a.split("=", 1)[1])
                if a.startswith("size="):
                    size = a.split("=", 1)[1]
                if a.startswith("legend="):
                    legend = a.split("=", 1)[1] not in {"0", "false", "no"}
                if a.startswith("color="):
                    color = a.split("=", 1)[1]
                if a.startswith("scale="):
                    scale = a.split("=", 1)[1]
                if a.startswith("gain="):
                    gain = float(a.split("=", 1)[1])

            # derive region
            start = proj.render_start if proj.render_start is not None else 0
            end = proj.render_end if proj.render_end is not None else project_song_end_tick(proj)
            if proj.loop_start is not None and proj.loop_end is not None:
                start, end = proj.loop_start, proj.loop_end
            render_proj = slice_project_range(proj, start, end)

            # render temp wav then spectrogram
            tmp_wav = Path(out_png).with_suffix(".tmp.wav")
            render_project_wav(render_proj, soundfont=sf, out_wav=str(tmp_wav), sample_rate=sr)
            render_spectrogram_png(tmp_wav, out_png, sample_rate=sr, opts=SpectrogramOptions(size=size, legend=legend, color=color, scale=scale, gain=gain))

            # write band report
            rep = band_energy_report(tmp_wav)
            Path(out_png).with_suffix(".bands.txt").write_text(
                "\n".join(
                    [
                        f"project: {proj.name}",
                        f"region_ticks: {start}..{end}",
                        f"full.mean_db={rep['full']['mean_volume']:.1f} full.max_db={rep['full']['max_volume']:.1f}",
                        f"sub<90.mean_db={rep['sub_lt90']['mean_volume']:.1f} sub<90.max_db={rep['sub_lt90']['max_volume']:.1f}",
                        f"rest>=90.mean_db={rep['rest_ge90']['mean_volume']:.1f} rest>=90.max_db={rep['rest_ge90']['max_volume']:.1f}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            tmp_wav.unlink(missing_ok=True)
            return

        if cmd == "analyze_refs":
            # analyze_refs <out.json>
            out = Path(args[0])
            issues = [i.__dict__ for i in analyze_references(proj)]
            out.write_text(__import__("json").dumps({"issues": issues}, indent=2, sort_keys=True) + "\n")
            return

        if cmd == "validate_project":
            # validate_project (in-place, best-effort)
            self.ctx.project = validate_and_migrate_project(proj)
            self.ctx.project.dirty = True
            return

        if cmd == "diff_projects":
            # diff_projects <a.json> <b.json> <out.diff>
            import difflib

            a = Path(args[0]).read_text(encoding="utf-8").splitlines(keepends=True)
            b = Path(args[1]).read_text(encoding="utf-8").splitlines(keepends=True)
            diff = difflib.unified_diff(a, b, fromfile=args[0], tofile=args[1])
            Path(args[2]).write_text("".join(diff), encoding="utf-8")
            return

        if cmd == "dump_state":
            out = Path(args[0])
            payload = proj.to_dict()
            end_tick = project_song_end_tick(proj)
            payload["derived"] = {
                "song_length_ticks": end_tick,
                "song_length_seconds": song_length_seconds(proj, end_tick),
                "song_bars_estimate": bars_estimate(proj, end_tick),
            }
            out.write_text(__import__("json").dumps(payload, indent=2, sort_keys=True) + "\n")
            return

        raise ValueError(f"Unknown command: {cmd}")

    def require_project(self) -> Project:
        if not self.ctx.project:
            raise RuntimeError("No project")
        return self.ctx.project


def read_lines_from_path_or_stdin(path: str | None) -> list[str]:
    if path and path != "-":
        return Path(path).read_text(encoding="utf-8").splitlines()
    return sys.stdin.read().splitlines()


def script_base_dir(path: str | None) -> Path | None:
    if path and path != "-":
        return Path(path).expanduser().resolve().parent
    return None
