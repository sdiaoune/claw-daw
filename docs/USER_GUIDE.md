# claw-daw User Guide

claw-daw is an offline, deterministic, terminal-first MIDI “DAW” MVP.

It’s designed for two workflows:

1) **Interactive TUI**: sketch/iterate quickly
2) **Headless scripts**: generate/edit/export projects non-interactively (great for automation/agents)

---

## Concepts

### Project
A project is a human-readable JSON file containing:
- global settings (BPM, swing, loop/render region)
- a list of tracks
- per-track notes and/or patterns/clips

### Time model (ticks / PPQ)
Time is expressed in **ticks**.

Defaults:
- `PPQ = 480`
- `1 beat (quarter note) = 480 ticks`
- `1 bar (4/4) = 1920 ticks`
- `1/16 note = 120 ticks`

Practical conversions (4/4):
- `bar_ticks = 1920`
- `beat_ticks = 480`
- `sixteenth_ticks = 120`

### Tracks
A track is either:
- a **GM instrument** (MIDI program + optional reverb/chorus/pan/volume)
- or a **sampler** track for drums/808 (see “Sampler support”)

### Patterns and clips (arrangement mode)
Instead of writing one long note list, claw-daw encourages **patterns** and **clips**:

- **Pattern**: a named chunk of notes (often 1–4 bars)
- **Clip**: a placement of a pattern at a time position (optionally repeated)

This makes projects more editable and deterministic.

---

## Installation

### Python
- Python **3.10+**

### System dependencies
- `fluidsynth` (renders MIDI → WAV)
- `ffmpeg` (encodes WAV → MP3/M4A, applies light mastering presets)

Linux (Debian/Ubuntu):

```bash
sudo apt-get install fluidsynth ffmpeg
sudo apt-get install fluid-soundfont-gm
```

macOS:

```bash
brew install fluidsynth ffmpeg
# then download a GM .sf2 soundfont
```

### SoundFont (.sf2)
You need a GM SoundFont.

If `/usr/share/sounds/sf2/default-GM.sf2` exists, it’s used automatically.

Otherwise, provide one via CLI:

```bash
claw-daw --soundfont /path/to/your.sf2
```

---

## Running the TUI

```bash
claw-daw
```

Key controls (high-level):
- `?` help
- `:` command mode
- `q` / `Esc` quit
- `g` toggle view (tracks ↔ arrange)
- `1` tracks view, `2` arrange view
- `Space` play/stop
- `m` mute selected track
- `s` solo selected track
- `c` toggle metronome
- `C` cycle count-in (0 → 1 → 2 bars)

### Command mode
Press `:` then enter commands (same language used by headless scripts).

Tip: build muscle memory by doing *everything* through `:` first; it keeps workflows portable.

---

## Headless (scripted) usage

Run a script and export audio without opening the UI:

```bash
claw-daw --headless \
  --soundfont /usr/share/sounds/sf2/default-GM.sf2 \
  --script templates/hiphop_1min.txt
```

Scripts are plain text files containing one command per line.

---

## Prompting workflows

### Recommended: prompt an agent, not the DAW

For best results, treat **claw-daw as the workstation**.
You prompt an agent with a producer brief, and the agent uses claw-daw (headless scripts + iteration) to build the track.

### Optional: `claw-daw prompt` → script (offline)

claw-daw also includes an **offline, deterministic prompt→script helper** that turns a natural-language prompt into a headless script.
It’s useful for scaffolding, but it won’t replace a musically intentional agent loop.

It supports:
- prompt → structured brief → script generator
- style presets (tempo/swing/density/mastering defaults)
- novelty constraints via project similarity scoring
- optional closed-loop preview → analyze → auto-tune iteration

Generate a script (no audio render):

```bash
claw-daw prompt --out my_prompt_song --prompt "dark lofi beat, 78bpm, A minor" \
  --iters 3 --max-similarity 0.92
# writes: tools/my_prompt_song.txt
```

Generate + render preview + mp3 (requires --soundfont):

```bash
SF2=$(claw-daw paths --soundfont | head -n 1)
claw-daw prompt --out my_prompt_song --prompt "house 124bpm" --render --soundfont "$SF2"
# writes: tools/my_prompt_song.txt + out/my_prompt_song.preview.mp3 + out/my_prompt_song.mp3
```

---

## Command reference (practical)

### Create/open/save
- `new_project <name> [bpm]`
- `open_project <path>`
- `save_project [path]`

### Add/remove tracks
- `add_track <name> [program|gm_name]`
- `delete_track <index>`

`program` is MIDI program number (0–127 or 1–128 depending on the parser).
You can also use common GM names like `piano`, `bass`, etc.

### Mixer
- `set_program <track_index> <program>`
- `set_volume <track_index> <0-127>`
- `set_pan <track_index> <0-127>`
- `set_reverb <track_index> <0-127>`
- `set_chorus <track_index> <0-127>`

### Built-in sampler presets (deterministic)
If a track is in sampler mode, you can choose a preset:
- `set_sampler_preset <track_index> <preset>`
- convenience: `set_kit <track_index> <preset>` and `set_808 <track_index> <preset>`

Examples:
- 808 presets: `clean` (default), `dist`, `growl`

### Timing
- `set_swing <0-75>`
- `set_loop <start> <end>` / `clear_loop`
- `set_render_region <start> <end>` / `clear_render_region`

`<start>`/`<end>` can be raw ticks (`960`) **or** bar:beat timecodes (`2:0` == bar 2 beat 0 in 4/4).
You can also use `bar:beat:tick` (e.g. `1:2:120`).

### Patterns / arrangement
- `new_pattern <track> <name> <length>`
- `add_note_pat <track> <pattern> <pitch> <start> <dur> [vel] [chance=..] [mute=0|1] [accent=..] [glide_ticks=..]`
- `place_pattern <track> <pattern> <start> [repeats]`

`<length>`/`<start>`/`<dur>` support ticks or bar:beat syntax.

Editing clips/patterns:
- `move_clip <track> <clip_index> <new_start>`
- `delete_clip <track> <clip_index>`
- `copy_bars <track> <src_bar> <bars> <dst_bar>`
- `rename_pattern <track> <old> <new>`
- `duplicate_pattern <track> <src> <dst>`
- `delete_pattern <track> <name>`
- `clear_clips <track>`

Agent-friendly note selection + transforms:
- `select_notes <track> <pattern> [filters...]` (filters: pitch/start/dur/vel with =,!=,>=,<=,>,<)
- `apply_selected <track> <pattern> op=shift ticks=<time>`
- `apply_selected <track> <pattern> op=transpose semis=<int>`
- `apply_selected <track> <pattern> op=vel_scale factor=<float>`
- `apply_selected <track> <pattern> op=set mute=<0|1> chance=<0..1> accent=<float> glide_ticks=<ticks>`

Pattern transform primitives:
- `pattern_transpose <track> <pattern> <semitones>`
- `pattern_shift <track> <pattern> <ticks|bar:beat>`
- `pattern_stretch <track> <pattern> <factor>`
- `pattern_reverse <track> <pattern>`
- `pattern_vel <track> <pattern> <scale>`

### Drum generator
- `gen_drums <track> <pattern> <length_ticks> <style> seed=0 density=0.8`

Styles: `hiphop|lofi|house`

### Export
- `export_midi <path>`
- `export_wav [path|"-"] preset=demo|clean|lofi fade=0.15 trim=60 sr=44100` (use `-` to stream WAV to stdout)
- `export_mp3 [path|"-"] preset=demo|clean|lofi fade=0.15 trim=60 sr=44100 br=192k` (use `-` to stream MP3 to stdout)
- `export_m4a [path|"-"] preset=demo|clean|lofi fade=0.15 trim=60 sr=44100 br=192k` (use `-` to stream M4A to stdout)
- `export_preview_mp3 <path|"-"] bars=<n> start=<bar:beat> preset=demo|clean|lofi sr=44100 br=192k`
- `analyze_audio <in_audio> <out.json>`
- `export_stems <dir>`

Notes:
- `trim` is optional; when set, exports are limited to N seconds.
- `fade` applies an end fade.
- Mastering is intentionally light and deterministic.

---

## Sampler support (drum one-shots)

Sampler mode is currently **restricted** to built-in sampler types.

Command:

- `set_sampler <track_index> <drums|808|none>`
- `set_glide <track_index> <ticks|bar:beat>` (808 only)
- `set_humanize <track_index> timing=<ticks> velocity=<ticks> seed=<int>`

This is meant for:
- drum hits: kick/snare/hat/percs
- 808-style one-shots

**Not yet supported**:
- browsing/loading a `.zip` sample pack directly from the TUI
- multi-sampled “real instruments” sample libraries (unless packaged as a SoundFont)

---

## Arrangement helpers: sections + variations

These are optional metadata you can use to label parts and swap patterns per section.

- `add_section <name> <start> <length>`
- `add_variation <section_name> <track_index> <src_pattern> <dst_pattern>`

At export time, if a clip starts inside a section with a matching variation rule,
`src_pattern` is replaced with `dst_pattern` for that track.

## Agent-native utilities (lint/diff/validation)

These commands are designed for automated workflows:

- `analyze_refs <out.json>` — detect missing pattern references / unused patterns
- `validate_project` — best-effort clamp/migrate in-memory project
- `diff_projects <a.json> <b.json> <out.diff>` — produce a unified diff

---

## Troubleshooting

### “Exports/playback error: no soundfont”
Provide a SoundFont:

```bash
claw-daw --soundfont /path/to/GM.sf2
```

### “No audio” / “fluidsynth not found”
Install fluidsynth:

```bash
sudo apt-get install fluidsynth
```

### MP3 export fails
Ensure `ffmpeg` is installed:

```bash
sudo apt-get install ffmpeg
```

### Renders are slow
Audio rendering is CPU-bound (fluidsynth + ffmpeg). Try:
- shorter render region (`set_render_region`)
- lower complexity (fewer tracks)

---

## Examples

### A minimal 8-bar loop

```txt
new_project demo 90
add_track Drums 0
set_sampler 0 drums
new_pattern 0 d 1920
# kick on 1 and 3
add_note_pat 0 d 36 0 180 110
add_note_pat 0 d 36 960 180 105
# snare on 2 and 4
add_note_pat 0 d 38 480 150 95
add_note_pat 0 d 38 1440 150 95
place_pattern 0 d 0 8
export_mp3 out/demo.mp3 preset=clean
```

### Browse more examples
- `templates/*.txt` — starter scripts
- `tools/*.txt` — longer “song scripts” used during development
- `docs/AGENT_COOKBOOK.md` — deeper notes for automated/headless workflows
