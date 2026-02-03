from __future__ import annotations

import curses
import shlex
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from claw_daw.arrange.types import Clip, Pattern
from claw_daw.audio.fluidsynth_cli import PlaybackHandle, play_midi, render_wav
from claw_daw.audio.stems import export_stems
from claw_daw.io.midi import export_midi
from claw_daw.io.project_json import load_project, save_project
from claw_daw.model.types import Note, Project, Track
from claw_daw.tui.helptext import HELP_TEXT
from claw_daw.util.gm import parse_program
# (unused) slice_project_loop was removed from imports
from claw_daw.util.region import slice_project_range
from claw_daw.util.derived import project_song_end_tick
from claw_daw.util.soundfont import find_default_soundfont
from claw_daw.util.quantize import parse_grid, quantize_project_track
from claw_daw.util.limits import MAX_TRACKS, MAX_PATTERNS_PER_TRACK, MAX_CLIPS_PER_TRACK, MAX_NOTES_PER_PATTERN


@dataclass
class UndoAction:
    kind: str
    payload: dict


class DawApp:
    """Curses TUI.

    Focused on being agent-drivable via ':' command mode.
    """

    def __init__(self, stdscr: "curses._CursesWindow") -> None:
        self.stdscr = stdscr
        self.project: Project | None = None
        self.selected_track: int = 0
        self.mode: str = "normal"  # normal|command|help|prompt|confirm_quit
        self.view: str = "tracks"  # tracks|arrange
        self.cmd_buffer: str = ""
        self.prompt: str = ""
        self.status: str = ""

        self.soundfont: str | None = None
        self.playback: PlaybackHandle | None = None
        self.playback_start_ts: float | None = None

        self.undo_stack: list[UndoAction] = []

        self.metronome_enabled: bool = False
        self.count_in_bars: int = 0

    # -------- lifecycle --------

    def run(self) -> None:
        curses.curs_set(0)
        self.stdscr.nodelay(False)
        self.stdscr.keypad(True)

        # prompt for soundfont on first run, default to system GM
        default_sf = find_default_soundfont()
        if default_sf:
            self.soundfont = default_sf

        while True:
            self.draw()
            ch = self.stdscr.getch()
            if not self.handle_key(ch):
                break

        self.stop_playback()

    # -------- draw --------

    def draw(self) -> None:
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()

        self.stdscr.addstr(0, 0, "claw-daw"[: w - 1], curses.A_BOLD)

        proj = self.project
        if proj:
            dirty = "*" if proj.dirty else ""
            loop = ""
            if proj.loop_start is not None and proj.loop_end is not None:
                loop = f" loop={proj.loop_start}..{proj.loop_end}"
            header = (
                f"View:{self.view}  Track:{self.selected_track}  "
                f"Project:{proj.name}{dirty}  tempo={proj.tempo_bpm}  ppq={proj.ppq}  swing={proj.swing_percent}%{loop}  metro={int(self.metronome_enabled)}  count_in={self.count_in_bars}b"
            )
        else:
            header = f"View:{self.view}  Track:{self.selected_track}  Project:<none> (use :new_project <name>)"
        self.stdscr.addstr(1, 0, header[: w - 1])

        left_w = max(34, w // 3)
        right_x = left_w + 1

        # Track list
        self.stdscr.addstr(3, 0, "Tracks", curses.A_UNDERLINE)
        if proj:
            for i, t in enumerate(proj.tracks):
                y = 4 + i
                if y >= h - 3:
                    break
                sel = curses.A_REVERSE if (self.mode == "normal" and i == self.selected_track) else 0
                flags = ("M" if t.mute else "-") + ("S" if t.solo else "-")
                label = (
                    f"{i}: {t.name} Ch{t.channel+1} P{t.program:03d} "
                    f"V{t.volume:03d} Pan{t.pan:03d} R{t.reverb:03d} C{t.chorus:03d} [{flags}]"
                )
                self.stdscr.addstr(y, 0, label[: left_w - 1], sel)

        # Right panel: either Tracks/Mixer or Arrange
        if self.view == "tracks":
            self.stdscr.addstr(3, right_x, "Tracks/Mixer", curses.A_UNDERLINE)
            if proj and proj.tracks:
                t = proj.tracks[self.selected_track]
                y = 4
                self.stdscr.addstr(y, right_x, f"Track: {t.name}"[: w - right_x - 1])
                y += 1
                self.stdscr.addstr(
                    y,
                    right_x,
                    f"program={t.program} vol={t.volume} pan={t.pan} reverb={t.reverb} chorus={t.chorus}"[: w - right_x - 1],
                )
                y += 2
                self.stdscr.addstr(y, right_x, f"Legacy notes: {len(t.notes)}"[: w - right_x - 1])
                y += 1
                for idx, n in enumerate(sorted(t.notes)[: max(0, h - y - 6)]):
                    self.stdscr.addstr(
                        y + idx,
                        right_x,
                        f"{idx}: p={n.pitch} st={n.start} dur={n.duration} v={n.velocity}"[: w - right_x - 1],
                    )
            else:
                self.stdscr.addstr(4, right_x, "(no tracks)"[: w - right_x - 1])
        else:
            self.stdscr.addstr(3, right_x, "Arrange (patterns + clips)", curses.A_UNDERLINE)
            if proj and proj.tracks:
                t = proj.tracks[self.selected_track]
                y = 4
                self.stdscr.addstr(y, right_x, "Patterns:"[: w - right_x - 1])
                y += 1
                for name, pat in list(t.patterns.items())[: max(0, (h // 2) - 6)]:
                    self.stdscr.addstr(
                        y,
                        right_x,
                        f"{name}: len={pat.length} notes={len(pat.notes)}"[: w - right_x - 1],
                    )
                    y += 1
                y += 1
                self.stdscr.addstr(y, right_x, "Clips:"[: w - right_x - 1])
                y += 1
                for i, c in enumerate(t.clips[: max(0, h - y - 3)]):
                    self.stdscr.addstr(
                        y + i,
                        right_x,
                        f"{i}: pat={c.pattern} start={c.start} reps={c.repeats}"[: w - right_x - 1],
                    )
            else:
                self.stdscr.addstr(4, right_x, "(no tracks)"[: w - right_x - 1])

        # status line
        pos = self.playback_pos_text()
        self.stdscr.addstr(h - 2, 0, f"MODE={self.mode} {pos} {self.status}"[: w - 1], curses.A_DIM)

        if self.mode in {"command", "prompt"}:
            prefix = ":" if self.mode == "command" else self.prompt
            line = prefix + self.cmd_buffer
            self.stdscr.addstr(h - 1, 0, line[: w - 1])
            curses.curs_set(1)
            self.stdscr.move(h - 1, min(len(line), w - 2))
        elif self.mode == "confirm_quit":
            self.stdscr.addstr(h - 1, 0, "Unsaved changes. Save? (y)es/(n)o/(c)ancel"[: w - 1])
            curses.curs_set(0)
        elif self.mode == "help":
            self.draw_help(h, w)
            curses.curs_set(0)
        else:
            self.stdscr.addstr(
                h - 1,
                0,
                "1 tracks | 2 arrange | g toggle | m mute | s solo | c metro | C count-in | ? help | : commands | Space play/stop | q quit"[: w - 1],
                curses.A_DIM,
            )
            curses.curs_set(0)

        self.stdscr.refresh()

    def draw_help(self, h: int, w: int) -> None:
        lines = HELP_TEXT.strip("\n").splitlines()
        for i, line in enumerate(lines[: h - 2]):
            self.stdscr.addstr(2 + i, 0, line[: w - 1])

    # -------- input --------

    def handle_key(self, ch: int) -> bool:
        if self.mode == "help":
            self.mode = "normal"
            self.status = ""
            return True

        if self.mode == "confirm_quit":
            return self.handle_confirm_quit(ch)

        if self.mode in {"command", "prompt"}:
            return self.handle_text_input(ch)

        if ch in (ord("q"), 27):
            if self.project and self.project.dirty:
                self.mode = "confirm_quit"
                return True
            return False

        if ch == ord("?"):
            self.mode = "help"
            return True

        if ch == ord("1"):
            self.view = "tracks"
            return True

        if ch == ord("2"):
            self.view = "arrange"
            return True

        if ch == ord(":"):
            self.mode = "command"
            self.cmd_buffer = ""
            return True

        if ch == ord("g"):
            self.view = "arrange" if self.view == "tracks" else "tracks"
            return True

        if ch == ord("m"):
            if self.project and self.project.tracks:
                t = self.project.tracks[self.selected_track]
                t.mute = not t.mute
                self.project.dirty = True
            return True

        if ch == ord("s"):
            if self.project and self.project.tracks:
                t = self.project.tracks[self.selected_track]
                t.solo = not t.solo
                self.project.dirty = True
            return True

        if ch == ord("c"):
            self.metronome_enabled = not self.metronome_enabled
            self.status = "Metronome " + ("on" if self.metronome_enabled else "off")
            return True

        if ch == ord("C"):
            self.count_in_bars = (self.count_in_bars + 1) % 3
            self.status = f"Count-in: {self.count_in_bars} bar(s)"
            return True

        if ch == curses.KEY_UP:
            self.selected_track = max(0, self.selected_track - 1)
            return True

        if ch == curses.KEY_DOWN:
            if self.project and self.project.tracks:
                self.selected_track = min(len(self.project.tracks) - 1, self.selected_track + 1)
            return True

        if ch == ord(" "):
            if self.playback:
                self.stop_playback()
            else:
                self.start_playback()
            return True

        return True

    def handle_confirm_quit(self, ch: int) -> bool:
        if ch in (ord("c"), 27):
            self.mode = "normal"
            return True
        if ch in (ord("n"), ord("N")):
            return False
        if ch in (ord("y"), ord("Y")):
            if self.project:
                save_project(self.project)
            return False
        return True

    def handle_text_input(self, ch: int) -> bool:
        if ch in (curses.KEY_ENTER, 10, 13):
            text = self.cmd_buffer.strip()
            self.cmd_buffer = ""
            self.mode = "normal"
            if text:
                try:
                    self.run_command(text)
                except SystemExit:
                    return False
                except Exception as e:
                    self.status = f"Error: {e}"
            return True

        if ch == 27:
            self.mode = "normal"
            self.cmd_buffer = ""
            return True

        if ch in (curses.KEY_BACKSPACE, 127, 8):
            self.cmd_buffer = self.cmd_buffer[:-1]
            return True

        if 0 <= ch <= 255:
            self.cmd_buffer += chr(ch)
        return True

    # -------- commands --------

    def run_command(self, text: str) -> None:
        args = shlex.split(text)
        cmd, *rest = args

        if cmd in {"quit", "q"}:
            raise SystemExit

        if cmd == "new_project":
            name = rest[0] if rest else "Untitled"
            bpm = int(rest[1]) if len(rest) > 1 else 120
            self.project = Project(name=name, tempo_bpm=bpm)
            self.project.dirty = True
            self.selected_track = 0
            self.status = f"Created project {name}"
            return

        if cmd == "open_project":
            self.project = load_project(rest[0])
            self.selected_track = 0
            self.status = f"Opened {rest[0]}"
            return

        if cmd == "save_project":
            if not self.project:
                raise RuntimeError("No project")
            out = save_project(self.project, rest[0] if rest else None)
            self.status = f"Saved {out}"
            return

        if cmd == "add_track":
            proj = self.require_project()
            name = rest[0] if rest else f"Track {len(proj.tracks)+1}"
            program = parse_program(rest[1]) if len(rest) > 1 else 0
            if len(proj.tracks) >= MAX_TRACKS:
                raise RuntimeError(f"max tracks reached ({MAX_TRACKS})")
            ch = proj.next_free_channel()
            proj.tracks.append(Track(name=name, channel=ch, program=program))
            proj.dirty = True
            self.status = f"Added track {name}"
            return

        if cmd == "set_volume":
            proj = self.require_project()
            idx = int(rest[0])
            proj.tracks[idx].volume = max(0, min(127, int(rest[1])))
            proj.dirty = True
            return
        if cmd == "set_pan":
            proj = self.require_project()
            idx = int(rest[0])
            proj.tracks[idx].pan = max(0, min(127, int(rest[1])))
            proj.dirty = True
            return
        if cmd == "set_reverb":
            proj = self.require_project()
            idx = int(rest[0])
            proj.tracks[idx].reverb = max(0, min(127, int(rest[1])))
            proj.dirty = True
            return
        if cmd == "set_chorus":
            proj = self.require_project()
            idx = int(rest[0])
            proj.tracks[idx].chorus = max(0, min(127, int(rest[1])))
            proj.dirty = True
            return

        if cmd == "set_swing":
            proj = self.require_project()
            proj.swing_percent = max(0, min(75, int(rest[0])))
            proj.dirty = True
            return

        if cmd == "set_loop":
            proj = self.require_project()
            proj.loop_start = int(rest[0])
            proj.loop_end = int(rest[1])
            proj.dirty = True
            return

        if cmd == "clear_loop":
            proj = self.require_project()
            proj.loop_start = None
            proj.loop_end = None
            proj.dirty = True
            return

        if cmd == "set_render_region":
            proj = self.require_project()
            proj.render_start = int(rest[0])
            proj.render_end = int(rest[1])
            proj.dirty = True
            return

        if cmd == "clear_render_region":
            proj = self.require_project()
            proj.render_start = None
            proj.render_end = None
            proj.dirty = True
            return

        if cmd == "quantize_track":
            proj = self.require_project()
            idx = int(rest[0])
            grid = parse_grid(proj.ppq, rest[1])
            strength = float(rest[2]) if len(rest) > 2 else 1.0
            changed = quantize_project_track(proj, idx, grid, strength)
            self.status = f"Quantized {changed} notes"
            return

        # pattern commands
        if cmd == "new_pattern":
            proj = self.require_project()
            ti = int(rest[0])
            name = rest[1]
            length = int(rest[2])
            if len(proj.tracks[ti].patterns) >= MAX_PATTERNS_PER_TRACK:
                raise RuntimeError(f"max patterns reached ({MAX_PATTERNS_PER_TRACK})")
            proj.tracks[ti].patterns[name] = Pattern(name=name, length=length)
            proj.dirty = True
            return

        if cmd == "add_note_pat":
            proj = self.require_project()
            ti = int(rest[0])
            pat = proj.tracks[ti].patterns[rest[1]]
            pitch = int(rest[2])
            start = int(rest[3])
            dur = int(rest[4])
            vel = int(rest[5]) if len(rest) > 5 else 100
            if len(pat.notes) >= MAX_NOTES_PER_PATTERN:
                raise RuntimeError(f"max notes/pattern reached ({MAX_NOTES_PER_PATTERN})")
            pat.notes.append(Note(start=start, duration=dur, pitch=pitch, velocity=vel))
            proj.dirty = True
            return

        if cmd == "place_pattern":
            proj = self.require_project()
            ti = int(rest[0])
            name = rest[1]
            start = int(rest[2])
            reps = int(rest[3]) if len(rest) > 3 else 1
            if len(proj.tracks[ti].clips) >= MAX_CLIPS_PER_TRACK:
                raise RuntimeError(f"max clips reached ({MAX_CLIPS_PER_TRACK})")
            proj.tracks[ti].clips.append(Clip(pattern=name, start=start, repeats=reps))
            proj.dirty = True
            return

        if cmd == "move_clip":
            proj = self.require_project()
            ti = int(rest[0])
            ci = int(rest[1])
            proj.tracks[ti].clips[ci].start = int(rest[2])
            proj.dirty = True
            return

        if cmd == "delete_clip":
            proj = self.require_project()
            ti = int(rest[0])
            ci = int(rest[1])
            proj.tracks[ti].clips.pop(ci)
            proj.dirty = True
            return

        if cmd == "copy_bars":
            proj = self.require_project()
            ti = int(rest[0])
            src_bar = int(rest[1])
            bars = int(rest[2])
            dst_bar = int(rest[3])
            tpbar = proj.ppq * 4
            src_start = src_bar * tpbar
            src_end = src_start + bars * tpbar
            dst_start = dst_bar * tpbar
            delta = dst_start - src_start
            t = proj.tracks[ti]
            to_copy = [c for c in t.clips if src_start <= c.start < src_end]
            for c in to_copy:
                t.clips.append(Clip(pattern=c.pattern, start=c.start + delta, repeats=c.repeats))
            proj.dirty = True
            return

        if cmd == "rename_pattern":
            proj = self.require_project()
            ti = int(rest[0])
            old, new = rest[1], rest[2]
            t = proj.tracks[ti]
            pat = t.patterns.pop(old)
            pat.name = new
            t.patterns[new] = pat
            for c in t.clips:
                if c.pattern == old:
                    c.pattern = new
            proj.dirty = True
            return

        if cmd == "duplicate_pattern":
            proj = self.require_project()
            ti = int(rest[0])
            src, dst = rest[1], rest[2]
            t = proj.tracks[ti]
            psrc = t.patterns[src]
            pdst = Pattern(name=dst, length=psrc.length)
            pdst.notes = [Note(start=n.start, duration=n.duration, pitch=n.pitch, velocity=n.velocity) for n in psrc.notes]
            t.patterns[dst] = pdst
            proj.dirty = True
            return

        if cmd == "delete_pattern":
            proj = self.require_project()
            ti = int(rest[0])
            name = rest[1]
            t = proj.tracks[ti]
            t.patterns.pop(name)
            t.clips = [c for c in t.clips if c.pattern != name]
            proj.dirty = True
            return

        if cmd == "clear_clips":
            proj = self.require_project()
            ti = int(rest[0])
            proj.tracks[ti].clips = []
            proj.dirty = True
            return

        if cmd == "export_midi":
            export_midi(self.require_project(), rest[0])
            return

        if cmd == "export_wav":
            if not self.soundfont:
                raise RuntimeError("No SoundFont available. Install a GM .sf2 and/or set --soundfont in headless mode.")
            self.export_wav(rest[0])
            return

        if cmd == "export_stems":
            if not self.soundfont:
                raise RuntimeError("No SoundFont available. Install a GM .sf2 and/or set --soundfont in headless mode.")
            export_stems(self.require_project(), soundfont=self.soundfont, out_dir=rest[0])
            return

        if cmd == "help":
            self.mode = "help"
            return

        raise ValueError(f"Unknown command: {cmd}")

    def require_project(self) -> Project:
        if not self.project:
            raise RuntimeError("No project")
        return self.project

    # -------- playback/export --------

    def export_wav(self, path: str) -> None:
        proj = self.require_project()
        sf = self.soundfont or find_default_soundfont()
        if not sf:
            raise RuntimeError("No SoundFont available. Install a GM .sf2 and/or set --soundfont in headless mode.")
        tmp = tempfile.NamedTemporaryFile(prefix="claw-daw-", suffix=".mid", delete=False)
        tmp.close()
        midi_path = tmp.name
        try:
            export_midi(proj, midi_path)
            render_wav(sf, midi_path, path)
        finally:
            Path(midi_path).unlink(missing_ok=True)

    def playback_pos_text(self) -> str:
        proj = self.project
        if not (self.playback and self.playback_start_ts and proj):
            return ""
        elapsed = max(0.0, time.time() - self.playback_start_ts)
        ticks_per_second = (proj.tempo_bpm / 60.0) * proj.ppq
        tick = int(elapsed * ticks_per_second)
        return f"POS={tick}t"

    def stop_playback(self) -> None:
        if not self.playback:
            return
        temp_path = getattr(self.playback, "_temp_midi_path", None)
        self.playback.stop()
        self.playback = None
        self.playback_start_ts = None
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)
        self.status = "Stopped"

    def start_playback(self) -> None:
        proj = self.require_project()
        if not self.soundfont:
            raise RuntimeError("No SoundFont available. Install a GM .sf2 and/or set --soundfont in headless mode.")

        tmp = tempfile.NamedTemporaryFile(prefix="claw-daw-", suffix=".mid", delete=False)
        tmp.close()
        midi_path = tmp.name

        # Determine region: loop takes precedence, else explicit render region, else full song.
        if proj.loop_start is not None and proj.loop_end is not None and proj.loop_end > proj.loop_start:
            start, end = proj.loop_start, proj.loop_end
        elif proj.render_start is not None and proj.render_end is not None and proj.render_end > proj.render_start:
            start, end = proj.render_start, proj.render_end
        else:
            start, end = 0, project_song_end_tick(proj)

        play_proj = slice_project_range(proj, start, end)

        # Count-in: shift all notes forward and prepend a metronome track.
        count_in_ticks = self.count_in_bars * proj.ppq * 4
        if count_in_ticks > 0:
            for t in play_proj.tracks:
                for n in t.notes:
                    n.start += count_in_ticks

        if self.metronome_enabled or self.count_in_bars > 0:
            # MIDI channel 10 is drums (index 9).
            mt = Track(name="Metronome", channel=9, program=0, volume=110)
            beat = proj.ppq
            total_ticks = count_in_ticks + (end - start)
            click_note = 37  # side stick
            tick = 0
            while tick < total_ticks:
                vel = 115 if (tick // beat) % 4 == 0 else 85
                mt.notes.append(Note(start=tick, duration=max(1, beat // 8), pitch=click_note, velocity=vel))
                tick += beat
            play_proj.tracks.insert(0, mt)

        export_midi(play_proj, midi_path)

        self.playback = play_midi(self.soundfont, midi_path)
        setattr(self.playback, "_temp_midi_path", midi_path)
        self.playback_start_ts = time.time()
        self.status = "Playing"
