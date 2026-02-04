from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from random import Random

from claw_daw.arrange.sections import Section, Variation
from claw_daw.arrange.drum_macros import generate_drum_macro_pack
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
from claw_daw.util.drumkit import get_drum_kit, list_drum_kits
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
        # Selection state for agent-friendly edits.
        # Map: (track_index, pattern_name) -> list[note_index]
        self._selection: dict[tuple[int, str], list[int]] = {}

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

        if cmd in {"save_project", "export_project"}:
            # export_project is kept as a compatibility alias.
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

        # -------- sound engineering (mix spec helpers) --------

        if cmd == "set_bus":
            # set_bus <track_index> <bus>
            idx = int(args[0])
            proj.tracks[idx].bus = str(args[1]).strip().lower() or "music"
            proj.dirty = True
            return

        if cmd == "eq":
            # eq track=<i>|master type=bell|hp|lp f=<hz> q=<q> g=<db>
            from claw_daw.cli.mix_cmds import apply_master_eq, apply_track_eq

            kv = {}
            for a in args:
                if "=" in a:
                    k, v = a.split("=", 1)
                    kv[k.strip()] = v.strip()

            typ = kv.get("type", "bell")
            f = float(kv.get("f", "1000"))
            q = float(kv.get("q", "1.0"))
            g = float(kv.get("g", "0.0"))
            tgt = kv.get("track", None)
            if tgt is None and ("master" in args or kv.get("target") == "master"):
                apply_master_eq(proj, f_hz=f, q=q, g_db=g)
            else:
                if tgt is None:
                    raise ValueError("eq requires track=<index> or 'master'")
                apply_track_eq(proj, track=int(tgt), kind=typ, f_hz=f, q=q, g_db=g)
            proj.dirty = True
            return

        if cmd == "sidechain":
            # sidechain src=<i> dst=<j> threshold_db=-24 ratio=6 attack_ms=5 release_ms=120
            from claw_daw.cli.mix_cmds import apply_sidechain

            kv = {}
            for a in args:
                if "=" in a:
                    k, v = a.split("=", 1)
                    kv[k.strip()] = v.strip()
            apply_sidechain(
                proj,
                src_track=int(kv.get("src", "0")),
                dst_track=int(kv.get("dst", "1")),
                threshold_db=float(kv.get("threshold_db", "-24")),
                ratio=float(kv.get("ratio", "6")),
                attack_ms=float(kv.get("attack_ms", "5")),
                release_ms=float(kv.get("release_ms", "120")),
            )
            proj.dirty = True
            return

        if cmd == "transient":
            # transient track=<i>|master attack=<...> sustain=<...>
            from claw_daw.cli.mix_cmds import apply_transient

            kv = {}
            for a in args:
                if "=" in a:
                    k, v = a.split("=", 1)
                    kv[k.strip()] = v.strip()
            atk = float(kv.get("attack", "0"))
            sus = float(kv.get("sustain", "0"))
            if kv.get("track") is not None:
                apply_transient(proj, track=int(kv["track"]), attack=atk, sustain=sus)
            else:
                apply_transient(proj, track=None, attack=atk, sustain=sus)
            proj.dirty = True
            return

        if cmd == "apply_palette":
            # apply_palette <style> [mood=..]
            # Applies per-style TrackSound + mixer defaults to tracks by role name.
            # Roles are inferred from track.name (case-insensitive): drums,bass,keys,pad,lead.
            style = str(args[0]).strip().lower()
            mood = None
            for a in args[1:]:
                if a.startswith("mood="):
                    mood = a.split("=", 1)[1]

            from claw_daw.prompt.palette import select_track_preset

            for t in proj.tracks:
                role = str(t.name).strip().lower()
                if role not in {"drums", "bass", "keys", "pad", "lead"}:
                    continue
                preset = select_track_preset(role, style=style, mood=mood)

                # Sound selection
                snd = preset.sound
                if snd.program is not None:
                    t.program = int(snd.program)
                    # If switching to GM program, disable sampler unless explicitly requested.
                    t.sampler = None
                    t.sampler_preset = None
                if snd.sampler:
                    t.sampler = snd.sampler
                    t.sampler_preset = snd.sampler_preset

                # Mixer
                mix = preset.mix
                if mix.volume is not None:
                    t.volume = max(0, min(127, int(mix.volume)))
                if mix.pan is not None:
                    t.pan = max(0, min(127, int(mix.pan)))
                if mix.reverb is not None:
                    t.reverb = max(0, min(127, int(mix.reverb)))
                if mix.chorus is not None:
                    t.chorus = max(0, min(127, int(mix.chorus)))

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

        if cmd == "set_sampler_preset":
            # set_sampler_preset <track_index> <preset>
            idx = int(args[0])
            proj.tracks[idx].sampler_preset = str(args[1]).strip()
            proj.dirty = True
            return

        if cmd == "set_kit":
            # set_kit <track_index> <preset>
            # Convenience: sampler drums preset (synth timbre), not the role->MIDI kit.
            idx = int(args[0])
            proj.tracks[idx].sampler = "drums"
            proj.tracks[idx].sampler_preset = str(args[1]).strip()
            proj.dirty = True
            return

        if cmd == "set_drum_kit":
            # set_drum_kit <track_index> <trap_hard|house_clean|boombap_dusty>
            idx = int(args[0])
            kit = str(args[1]).strip()
            proj.tracks[idx].drum_kit = get_drum_kit(kit).name
            proj.dirty = True
            return

        if cmd == "list_drum_kits":
            # list_drum_kits
            # Writes a deterministic, human-readable list to stdout.
            # (Useful in headless/agent flows.)
            print("\n".join(list_drum_kits(include_internal=False)))
            return

        if cmd == "set_808":
            # set_808 <track_index> <preset>
            idx = int(args[0])
            proj.tracks[idx].sampler = "808"
            proj.tracks[idx].sampler_preset = str(args[1]).strip()
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
            pdst.notes = [
                Note(
                    start=n.start,
                    duration=n.duration,
                    pitch=n.pitch,
                    velocity=n.velocity,
                    role=getattr(n, "role", None),
                    chance=getattr(n, "chance", 1.0),
                    mute=getattr(n, "mute", False),
                    accent=getattr(n, "accent", 1.0),
                    glide_ticks=getattr(n, "glide_ticks", 0),
                )
                for n in psrc.notes
            ]
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
            # add_note_pat <track> <pattern> <pitch> <start> <dur> [vel] [chance=..] [mute=0|1] [accent=..] [glide_ticks=..]
            ti = int(args[0])
            pat = proj.tracks[ti].patterns[args[1]]
            if len(pat.notes) >= MAX_NOTES_PER_PATTERN:
                raise RuntimeError(f"max notes/pattern reached ({MAX_NOTES_PER_PATTERN})")
            role: str | None = None
            pitch = 0
            try:
                pitch = int(args[2])
            except Exception:
                role = str(args[2]).strip()
                pitch = 0

            start = _tick(proj, args[3])
            dur = _tick(proj, args[4])

            vel = 100
            rest = args[5:]
            if rest and (rest[0].lstrip("-").isdigit()) and ("=" not in rest[0]):
                vel = int(rest[0])
                rest = rest[1:]

            kv: dict[str, str] = {}
            for a in rest:
                if "=" not in a:
                    continue
                k, v = a.split("=", 1)
                kv[k.strip()] = v.strip()

            chance = float(kv.get("chance", "1.0"))
            mute = kv.get("mute", "0") not in {"0", "false", "no"}
            accent = float(kv.get("accent", "1.0"))
            glide_ticks = _tick(proj, kv.get("glide_ticks", "0")) if "glide_ticks" in kv else 0

            pat.notes.append(
                Note(
                    start=start,
                    duration=dur,
                    pitch=pitch,
                    velocity=vel,
                    role=role,
                    chance=chance,
                    mute=mute,
                    accent=accent,
                    glide_ticks=int(glide_ticks),
                )
            )
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

                # hats
                if style in {"house", "lofi", "hiphop", "boom_bap"}:
                    # 8ths for boom-bap, 16ths otherwise
                    if style == "boom_bap":
                        if s % 2 == 0 and rnd.random() < max(0.25, min(1.0, density)):
                            pat.notes.append(Note(start=tick, duration=step // 2, pitch=hat, velocity=62))
                    else:
                        if rnd.random() < max(0.2, min(1.0, density)):
                            pat.notes.append(Note(start=tick, duration=step // 2, pitch=hat, velocity=65))

                if style == "trap":
                    # Trap hats: dense 16ths + occasional 32nd rolls.
                    if rnd.random() < max(0.4, min(1.0, density + 0.1)):
                        pat.notes.append(Note(start=tick, duration=step // 2, pitch=hat, velocity=62))
                        # roll (32nd)
                        if rnd.random() < 0.12 * max(0.4, density):
                            pat.notes.append(Note(start=tick + step // 2, duration=step // 4, pitch=hat, velocity=55))

                # kick patterns
                if style == "house":
                    # four-on-the-floor
                    if s % 4 == 0:
                        pat.notes.append(Note(start=tick, duration=step, pitch=kick, velocity=110))
                elif style in {"hiphop", "boom_bap"}:
                    # boom-bap uses a slightly more stable downbeat kick.
                    if style == "boom_bap":
                        if s in {0, 6, 10, 14, 16, 22, 26, 30} and rnd.random() < density:
                            pat.notes.append(Note(start=tick, duration=step, pitch=kick, velocity=112))
                    else:
                        if s in {0, 6, 8, 14} and rnd.random() < density:
                            pat.notes.append(Note(start=tick, duration=step, pitch=kick, velocity=115))
                elif style == "trap":
                    # sparse + syncopated
                    if s in {0, 3, 7, 10, 13, 16, 19, 23, 27, 31} and rnd.random() < (0.35 + 0.55 * density):
                        pat.notes.append(Note(start=tick, duration=step, pitch=kick, velocity=118))
                else:  # lofi
                    if s in {0, 7, 10, 14} and rnd.random() < density:
                        pat.notes.append(Note(start=tick, duration=step, pitch=kick, velocity=100))

                # snares
                if style == "trap":
                    # halftime: beat 3 of each bar in a 2-bar pattern (steps 8, 24)
                    if s in {8, 24}:
                        pat.notes.append(Note(start=tick, duration=step, pitch=snare, velocity=108))
                elif style == "boom_bap":
                    # 2 and 4 each bar (steps 4, 12, 20, 28)
                    if s in {4, 12, 20, 28}:
                        pat.notes.append(Note(start=tick, duration=step, pitch=snare, velocity=110))
                else:
                    # snare on 2 and 4
                    if s % 8 == 4:
                        pat.notes.append(Note(start=tick, duration=step, pitch=snare, velocity=105))

            proj.dirty = True
            return

        if cmd == "gen_drum_macros":
            # gen_drum_macros <track> <base_pattern> [out_prefix=drums] [seed=0] [make=both|4|8]
            ti = int(args[0])
            base_pat = args[1]
            seed = 0
            out_prefix: str | None = None
            make = "both"
            for a in args[2:]:
                if a.startswith("seed="):
                    seed = int(a.split("=", 1)[1])
                elif a.startswith("out_prefix="):
                    out_prefix = a.split("=", 1)[1].strip() or None
                elif a.startswith("make="):
                    make = a.split("=", 1)[1].strip().lower() or "both"

            make_4 = make in {"both", "4", "v4"}
            make_8 = make in {"both", "8", "v8"}
            if not (make_4 or make_8):
                raise ValueError("make must be: both|4|8")

            t = proj.tracks[ti]
            generate_drum_macro_pack(
                t,
                base_pattern=base_pat,
                ppq=proj.ppq,
                seed=seed,
                out_prefix=out_prefix,
                make_4=make_4,
                make_8=make_8,
                max_patterns=MAX_PATTERNS_PER_TRACK,
            )
            proj.dirty = True
            return

        if cmd == "gen_bass_follow":
            # gen_bass_follow <track> <pattern> <length_ticks>
            #   roots=45,53,50,52 (MIDI note numbers; interpreted per bar, repeated)
            #   seed=0 gap_prob=0.12 glide_prob=0.25 cadence_bars=4 turnaround=1
            #   vel=98 vel_jitter=10 note_len=0:1 glide_ticks=0:0:90
            ti = int(args[0])
            name = args[1]
            length = _tick(proj, args[2])

            kv: dict[str, str] = {}
            for a in args[3:]:
                if "=" not in a:
                    continue
                k, v = a.split("=", 1)
                kv[k.strip()] = v.strip()

            roots_raw = kv.get("roots", "")
            if not roots_raw:
                raise ValueError("gen_bass_follow requires roots=... (comma-separated MIDI note numbers)")
            roots = [int(x.strip()) for x in roots_raw.split(",") if x.strip()]
            if not roots:
                raise ValueError("gen_bass_follow requires at least one root")

            seed = int(kv.get("seed", "0"))
            gap_prob = max(0.0, min(1.0, float(kv.get("gap_prob", "0.12"))))
            glide_prob = max(0.0, min(1.0, float(kv.get("glide_prob", "0.25"))))
            cadence_bars = max(1, int(kv.get("cadence_bars", "4")))
            turnaround = kv.get("turnaround", "1") not in {"0", "false", "no"}

            base_vel = max(1, min(127, int(kv.get("vel", "98"))))
            vel_jitter = max(0, min(30, int(kv.get("vel_jitter", "10"))))

            # Default duration is an 8th note.
            note_len = _tick(proj, kv.get("note_len", "0:0:240"))
            glide_ticks = _tick(proj, kv.get("glide_ticks", "0")) if "glide_ticks" in kv else 0

            rnd = Random(seed)

            t = proj.tracks[ti]
            if name not in t.patterns:
                if len(t.patterns) >= MAX_PATTERNS_PER_TRACK:
                    raise RuntimeError(f"max patterns reached ({MAX_PATTERNS_PER_TRACK})")
                t.patterns[name] = Pattern(name=name, length=length)
            pat = t.patterns[name]
            pat.length = length
            pat.notes = []

            tpbar = _ticks_per_bar(proj)
            step = proj.ppq // 4  # 16th
            bars = max(1, length // tpbar)

            # Simple, musical rhythmic templates (16th steps within a bar)
            templates: list[list[int]] = [
                [0, 8],
                [0, 6, 8, 14],
                [0, 4, 8, 12],
                [0, 10],
            ]

            last_pitch: int | None = None
            last_start: int | None = None

            def add_note(start: int, pitch: int, dur: int) -> None:
                nonlocal last_pitch, last_start
                vel = base_vel + rnd.randint(-vel_jitter, vel_jitter)
                vel = max(1, min(127, vel))
                gt = 0
                if glide_ticks:
                    gt = int(glide_ticks)
                elif getattr(t, "glide_ticks", 0):
                    gt = int(t.glide_ticks or 0)

                # Decide glide per-note (only if pitch changes, and close enough).
                use_glide = False
                if gt and last_pitch is not None and pitch != last_pitch:
                    if abs(int(pitch) - int(last_pitch)) <= 7 and rnd.random() < glide_prob:
                        use_glide = True

                pat.notes.append(
                    Note(
                        start=int(start),
                        duration=max(1, int(dur)),
                        pitch=int(pitch),
                        velocity=int(vel),
                        glide_ticks=int(gt if use_glide else 0),
                    )
                )
                last_pitch = int(pitch)
                last_start = int(start)

            for b in range(bars):
                bar_root = roots[b % len(roots)]
                tmpl = templates[int(rnd.random() * len(templates)) % len(templates)]

                # Ensure a stable downbeat, thin the rest via gap_prob
                for i, st16 in enumerate(tmpl):
                    if i > 0 and rnd.random() < gap_prob:
                        continue
                    start = b * tpbar + st16 * step
                    add_note(start, bar_root, note_len)

                # Cadence: at phrase ends, add a short approach into next root.
                if (b + 1) % cadence_bars == 0:
                    next_root = roots[(b + 1) % len(roots)]
                    # semitone or whole-step approach
                    approach = next_root - (1 if rnd.random() < 0.6 else 2)
                    add_note(b * tpbar + 15 * step, approach, step)

                # Turnaround: in the final bar, do a tiny walk into the loop.
                if turnaround and b == bars - 1:
                    next_root = roots[0]
                    add_note(b * tpbar + 12 * step, bar_root, step)
                    add_note(b * tpbar + 14 * step, bar_root + (2 if rnd.random() < 0.5 else -2), step)
                    add_note(b * tpbar + 15 * step, next_root, step)

            # Tighten durations so notes don't smear across the bar end unless intended.
            pat.notes.sort(key=lambda n: int(n.start))
            for i, n in enumerate(pat.notes[:-1]):
                nxt = pat.notes[i + 1]
                max_dur = max(1, int(nxt.start) - int(n.start))
                n.duration = min(int(n.duration), max_dur)

            proj.dirty = True
            return

        # -------- editing/util --------

        if cmd == "quantize_track":
            ti = int(args[0])
            grid = parse_grid(proj.ppq, args[1])
            strength = float(args[2]) if len(args) > 2 else 1.0
            quantize_project_track(proj, ti, grid, strength)
            return

        if cmd == "select_notes":
            # select_notes <track> <pattern> [filters...]
            # Filters support: pitch, start, dur, vel with operators (=,!=,>=,<=,>,<)
            # Example:
            #   select_notes 0 hats pitch=42 start>=1:0 start<2:0
            ti = int(args[0])
            pat_name = args[1]
            pat = proj.tracks[ti].patterns[pat_name]

            def parse_filter(tok: str):
                ops = [">=", "<=", "!=", ">", "<", "="]
                for op in ops:
                    if op in tok:
                        k, v = tok.split(op, 1)
                        return k.strip(), op, v.strip()
                raise ValueError(f"invalid filter: {tok}")

            def parse_val(key: str, raw: str):
                if key in {"start", "dur"}:
                    return _tick(proj, raw)
                return int(raw)

            def match(n: Note, key: str, op: str, raw: str) -> bool:
                if key == "pitch":
                    cur = int(n.pitch)
                    val = int(raw)
                elif key == "vel":
                    cur = int(n.velocity)
                    val = int(raw)
                elif key == "start":
                    cur = int(n.start)
                    val = _tick(proj, raw)
                elif key == "dur":
                    cur = int(n.duration)
                    val = _tick(proj, raw)
                else:
                    raise ValueError(f"unknown filter key: {key}")

                if op == "=":
                    return cur == val
                if op == "!=":
                    return cur != val
                if op == ">=":
                    return cur >= val
                if op == "<=":
                    return cur <= val
                if op == ">":
                    return cur > val
                if op == "<":
                    return cur < val
                return False

            filters = [parse_filter(t) for t in args[2:]]
            idxs: list[int] = []
            for i, n in enumerate(pat.notes):
                ok = True
                for k, op, v in filters:
                    ok = ok and match(n, k, op, v)
                if ok:
                    idxs.append(i)

            self._selection[(ti, pat_name)] = idxs
            return

        if cmd == "apply_selected":
            # apply_selected <track> <pattern> op=<...> [args...]
            # ops:
            # - shift ticks=<time>
            # - transpose semis=<int>
            # - vel_scale factor=<float>
            # - set mute=<0|1>
            # - set chance=<0..1>
            # - set accent=<float>
            # - set glide_ticks=<ticks>
            ti = int(args[0])
            pat_name = args[1]
            pat = proj.tracks[ti].patterns[pat_name]
            sel = self._selection.get((ti, pat_name), [])

            kv = {}
            for a in args[2:]:
                if "=" not in a:
                    continue
                k, v = a.split("=", 1)
                kv[k.strip()] = v.strip()

            op = kv.get("op")
            if not op:
                raise ValueError("apply_selected requires op=...")

            def clamp_vel(v: int) -> int:
                return max(1, min(127, int(v)))

            if op == "shift":
                ticks = _tick(proj, kv.get("ticks", "0"))
                for i in sel:
                    pat.notes[i].start = max(0, int(pat.notes[i].start) + int(ticks))
                proj.dirty = True
                return

            if op == "transpose":
                semis = int(kv.get("semis", "0"))
                for i in sel:
                    pat.notes[i].pitch = max(0, min(127, int(pat.notes[i].pitch) + semis))
                proj.dirty = True
                return

            if op == "vel_scale":
                factor = float(kv.get("factor", "1.0"))
                for i in sel:
                    pat.notes[i].velocity = clamp_vel(round(int(pat.notes[i].velocity) * factor))
                proj.dirty = True
                return

            if op == "set":
                if "mute" in kv:
                    m = kv.get("mute", "0") not in {"0", "false", "no"}
                    for i in sel:
                        pat.notes[i].mute = bool(m)
                if "chance" in kv:
                    ch = float(kv.get("chance", "1.0"))
                    for i in sel:
                        pat.notes[i].chance = max(0.0, min(1.0, ch))
                if "accent" in kv:
                    ac = float(kv.get("accent", "1.0"))
                    for i in sel:
                        pat.notes[i].accent = ac
                if "glide_ticks" in kv:
                    gt = int(_tick(proj, kv.get("glide_ticks", "0")))
                    for i in sel:
                        pat.notes[i].glide_ticks = max(0, gt)
                proj.dirty = True
                return

            raise ValueError(f"unknown op: {op}")

        # -------- export --------

        if cmd == "export_midi":
            if self.dry_run:
                return
            export_midi(proj, args[0])
            return

        if cmd == "export_wav":
            # export_wav [path|"-"] [preset=demo] [fade=0.15] [sr=44100] [trim=60]
            # Use "-" to stream WAV bytes to stdout.
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
            mix_path: str | None = None
            for a in args[1:] if out_wav == args[0] else args:
                if a.startswith("preset="):
                    preset = a.split("=", 1)[1]
                if a.startswith("fade="):
                    fade = float(a.split("=", 1)[1])
                if a.startswith("sr="):
                    sr = int(a.split("=", 1)[1])
                if a.startswith("trim="):
                    trim = float(a.split("=", 1)[1])
                if a.startswith("mix="):
                    mix_path = a.split("=", 1)[1]

            # presets may be built-in (clean/demo/lofi/...) or file-based (file:/path or @/path)
            if not (preset in MASTER_PRESETS or preset.startswith("file:") or preset.startswith("@")):
                raise ValueError(f"preset must be one of: {', '.join(sorted(MASTER_PRESETS))} or file:/path/to/afilter.txt")

            # derive region
            start = proj.render_start if proj.render_start is not None else 0
            end = proj.render_end if proj.render_end is not None else project_song_end_tick(proj)
            if proj.loop_start is not None and proj.loop_end is not None:
                start, end = proj.loop_start, proj.loop_end
            render_proj = slice_project_range(proj, start, end)

            stream = out_wav.strip() == "-"
            tmp_out = out_wav
            if stream:
                # Render to a temp wav, then master to stdout.
                tmp_out = str(Path(_default_export_path(proj, "wav")).with_suffix(".tmp.wav"))

            mix_spec = None
            if mix_path:
                mp = Path(mix_path).expanduser()
                raw = mp.read_text(encoding="utf-8")
                if mp.suffix.lower() in {".yaml", ".yml"}:
                    try:
                        import yaml  # type: ignore
                    except Exception as e:
                        raise RuntimeError("mix= requires PyYAML for .yaml/.yml") from e
                    mix_spec = yaml.safe_load(raw) or {}
                else:
                    import json

                    mix_spec = json.loads(raw or "{}")

            render_project_wav(render_proj, soundfont=sf, out_wav=tmp_out, sample_rate=sr, mix=mix_spec)

            # mastering + fades
            if stream:
                master_wav(tmp_out, "-", sample_rate=sr, trim_seconds=trim, preset=preset, fade_in_seconds=fade, fade_out_seconds=fade)
                Path(tmp_out).unlink(missing_ok=True)
                return

            norm = Path(out_wav).with_suffix(".master.wav")
            mastered = master_wav(tmp_out, str(norm), sample_rate=sr, trim_seconds=trim, preset=preset, fade_in_seconds=fade, fade_out_seconds=fade)
            if mastered != out_wav:
                Path(out_wav).unlink(missing_ok=True)
                Path(mastered).rename(out_wav)
            return

        if cmd == "export_preview_mp3":
            # export_preview_mp3 <out.mp3|"-"] bars=<n> start=<bar:beat> [preset=demo] [sr=44100] [br=192k]
            # Convenience for agent loops.
            if self.dry_run:
                return
            sf = self.ctx.soundfont
            if not sf:
                raise RuntimeError("soundfont not set")

            out_mp3 = args[0]
            bars = 8
            start_tick = 0
            sr = 44100
            br = "192k"
            preset = "demo"
            for a in args[1:]:
                if a.startswith("bars="):
                    bars = int(a.split("=", 1)[1])
                if a.startswith("start="):
                    start_tick = _tick(proj, a.split("=", 1)[1])
                if a.startswith("sr="):
                    sr = int(a.split("=", 1)[1])
                if a.startswith("br="):
                    br = a.split("=", 1)[1]
                if a.startswith("preset="):
                    preset = a.split("=", 1)[1]

            end_tick = start_tick + bars * _ticks_per_bar(proj)
            render_proj = slice_project_range(proj, start_tick, end_tick)

            tmp_wav = Path(_default_export_path(proj, "wav")).with_suffix(".preview.tmp.wav")
            render_project_wav(render_proj, soundfont=sf, out_wav=str(tmp_wav), sample_rate=sr)
            norm = tmp_wav.with_suffix(".master.wav")
            mastered = master_wav(str(tmp_wav), str(norm), sample_rate=sr, trim_seconds=None, preset=preset, fade_in_seconds=0.0, fade_out_seconds=0.0)
            encode_audio(str(mastered), out_mp3, trim_seconds=None, sample_rate=sr, codec="mp3", bitrate=br)
            Path(tmp_wav).unlink(missing_ok=True)
            Path(mastered).unlink(missing_ok=True)
            return

        if cmd == "export_mp3":
            # export_mp3 [out.mp3|"-"] [trim=60] [sr=44100] [br=192k] [preset=demo] [fade=0.15] [mix=tools/mix.json]
            # Use "-" to stream MP3 bytes to stdout.
            if self.dry_run:
                return
            sf = self.ctx.soundfont
            if not sf:
                raise RuntimeError("soundfont not set")

            out_mp3 = args[0] if args and (args[0].endswith(".mp3") or args[0] == "-") else _default_export_path(proj, "mp3")
            sr = 44100
            trim = None
            br = "192k"
            preset = "demo"
            fade = 0.0
            mix_path: str | None = None
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
                if a.startswith("mix="):
                    mix_path = a.split("=", 1)[1]

            tmp_wav = Path(_default_export_path(proj, "wav")).with_suffix(".tmp.wav") if out_mp3 == "-" else Path(out_mp3).with_suffix(".tmp.wav")
            cmdline = f"export_wav {tmp_wav} preset={preset} fade={fade} sr={sr}" + (f" trim={trim}" if trim else "")
            if mix_path:
                cmdline += f" mix={mix_path}"
            self.run_command(cmdline)
            encode_audio(str(tmp_wav), out_mp3, trim_seconds=None, sample_rate=sr, codec="mp3", bitrate=br)
            tmp_wav.unlink(missing_ok=True)
            return

        if cmd == "export_m4a":
            # export_m4a [out.m4a|"-"] [trim=60] [sr=44100] [br=192k] [preset=demo] [fade=0.15] [mix=tools/mix.json]
            # Use "-" to stream M4A bytes to stdout.
            if self.dry_run:
                return
            sf = self.ctx.soundfont
            if not sf:
                raise RuntimeError("soundfont not set")

            out_m4a = args[0] if args and (args[0].endswith(".m4a") or args[0] == "-") else _default_export_path(proj, "m4a")
            sr = 44100
            trim = None
            br = "192k"
            preset = "demo"
            fade = 0.0
            mix_path: str | None = None
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
                if a.startswith("mix="):
                    mix_path = a.split("=", 1)[1]

            tmp_wav = Path(_default_export_path(proj, "wav")).with_suffix(".tmp.wav") if out_m4a == "-" else Path(out_m4a).with_suffix(".tmp.wav")
            cmdline = f"export_wav {tmp_wav} preset={preset} fade={fade} sr={sr}" + (f" trim={trim}" if trim else "")
            if mix_path:
                cmdline += f" mix={mix_path}"
            self.run_command(cmdline)
            encode_audio(str(tmp_wav), out_m4a, trim_seconds=None, sample_rate=sr, codec="m4a", bitrate=br)
            tmp_wav.unlink(missing_ok=True)
            return

        if cmd == "export_stems":
            sf = self.ctx.soundfont
            if not sf:
                raise RuntimeError("soundfont not set for headless export_stems")
            export_stems(proj, soundfont=sf, out_dir=args[0])
            return

        if cmd == "export_busses":
            # export_busses <out_dir>
            sf = self.ctx.soundfont
            if not sf:
                raise RuntimeError("soundfont not set for headless export_busses")
            from claw_daw.audio.stems import export_busses

            export_busses(proj, soundfont=sf, out_dir=args[0])
            return

        if cmd == "meter_audio":
            # meter_audio <in_audio> <out.json> [spectral=1]
            # Writes a JSON report with LUFS/true-peak/LRA, peak/RMS, crest factor, DC offset,
            # stereo correlation, and (optionally) coarse spectral band stats.
            if self.dry_run:
                return
            import json

            from claw_daw.audio.metering import analyze_metering

            include_spectral = True
            for a in args[2:]:
                if a.startswith("spectral="):
                    include_spectral = a.split("=", 1)[1] not in {"0", "false", "no"}

            rep = analyze_metering(args[0], include_spectral=include_spectral)
            Path(args[1]).write_text(json.dumps(rep.__dict__, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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

        if cmd == "analyze_audio":
            # analyze_audio <in_audio> <out.json>
            if self.dry_run:
                return
            inp = args[0]
            out_json = args[1]
            import json

            rep = band_energy_report(inp)
            Path(out_json).parent.mkdir(parents=True, exist_ok=True)
            Path(out_json).write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
