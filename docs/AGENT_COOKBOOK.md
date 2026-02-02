# Agent Cookbook — claw-daw

claw-daw is an offline, deterministic, terminal-first MIDI DAW that agents can drive via **headless scripts**.

## Quick start

```bash
claw-daw --headless \
  --soundfont /usr/share/sounds/sf2/default-GM.sf2 \
  --script templates/hiphop_1min.txt
```

## How agents should use claw-daw (recommended)

For the full “agent-as-producer” workflow and checklists, see:
- `docs/AGENT_PLAYBOOK.md`

Treat **claw-daw as the workstation**, not the “thing you prompt.”

- The **user prompts the agent** (you) with a producer brief (style, BPM, key, sections, palette, deliverables).
- The **agent writes/edits a headless script** (patterns + clips), renders, listens, tweaks, and re-renders.
- Output artifacts stay deterministic and reviewable: JSON + MIDI + audio.

This mirrors how a good producer works: intent → arrangement → sound choices → iteration.

### Minimal agent loop

1) Write `tools/<name>.txt`
2) Render: `claw-daw --headless --soundfont <SF2> --script tools/<name>.txt`
3) Iterate: change the script (or use `select_notes` + `apply_selected`) and rerender.

## Optional: claw-daw prompt (helper, not a replacement)

claw-daw includes an **offline prompt→script helper** for quick scaffolding. It’s best treated as a starting point, not the final result.

```bash
claw-daw prompt --out prompt_v1 \
  --prompt "late-night hiphop at 74bpm, dark, A minor" \
  --iters 3 --max-similarity 0.92
# tools/prompt_v1.txt
```

## Time model (ticks / PPQ)

- Default `PPQ=480`
- `1 beat (quarter note) = 480 ticks`
- In 4/4: `1 bar = 4 beats = 1920 ticks`
- 16ths: `PPQ/4 = 120 ticks`

Practical conversions (4/4):
- `bar_ticks = ppq*4`
- `beat_ticks = ppq`
- `sixteenth_ticks = ppq//4`

## Swing semantics

`set_swing <0-75>` applies swing by delaying **odd 16th steps** (offbeat 16ths).
- `0` = straight
- `15–30` = typical hiphop/lofi feel

Swing is applied during MIDI rendering (export/playback), not by permanently rewriting notes.

## Loop vs render region

- `set_loop a b` / `clear_loop`
  - primarily for **playback looping**
  - takes precedence over render region in headless exports

- `set_render_region a b` / `clear_render_region`
  - defines an explicit export window `[a,b)` in ticks
  - useful for "render only bars 8–16" workflows

If neither is set, exports render the whole song up to the derived end tick.

## Arrangement model

Each track can be either:
- **Linear notes** (`insert_note`) OR
- **Arrangement**: patterns + clips

Patterns:
- `new_pattern <track> <name> <length_ticks>`
- `add_note_pat ...`

Clips:
- `place_pattern <track> <pattern> <start_tick> [repeats]`

Key idiom: keep patterns short (1–2 bars), then place them repeatedly.

### Useful arrangement ops

- `copy_bars <track> <src_bar> <bars> <dst_bar>` — copies clips whose start is inside the bar range
- `move_clip <track> <clip_index> <new_start>`
- `delete_clip <track> <clip_index>`
- `rename_pattern`, `duplicate_pattern`, `delete_pattern`

## Determinism guidelines

For shareable, repeatable outputs:
- Prefer patterns + clips (avoid long linear note lists)
- Use deterministic generators (`gen_drums ... seed=N`)
- Avoid real-time randomness or timestamps in filenames

## Common workflow (agent)

1) Create project + tracks
2) Create 1-bar patterns (drums/bass/keys)
3) Place patterns across ~24 bars (≈60s at ~96 BPM)
4) Export mp3 and dump state

Example skeleton:

```txt
new_project demo 96
add_track Drums 0
new_pattern 0 d 1920
# ...add_note_pat...
place_pattern 0 d 0 24
export_mp3 trim=60 preset=demo fade=0.15
save_project demo.json
dump_state demo_state.json
```

## Drum generation utility

`gen_drums <track> <pattern> <length_ticks> <style> seed=0 density=0.8`

- `style`: `hiphop|lofi|house`
- deterministic (`seed`)
- writes kick/snare/hats pattern using 16th grid

## Export and stems

Audio export uses:
- `fluidsynth` for MIDI→WAV
- `ffmpeg` for mastering + encoding

Commands:
- `export_wav [path] preset=demo|clean|lofi fade=0.15 trim=60`
- `export_mp3 [path] preset=...`
- `export_m4a [path] preset=...`
- `export_stems <dir>`

Mastering presets:
- `demo` (-16 LUFS-ish)
- `clean` (quieter, less aggressive)
- `loud` (hotter)

## Shareability helpers

`render_demo <style> <out_prefix>` writes:
- `<out_prefix>.mp3` (60s)
- `<out_prefix>.mid`
- `<out_prefix>.json`
- `<out_prefix>_cover.txt`

Shortcuts:
- `template_house <out_prefix>`
- `template_lofi <out_prefix>`
- `template_hiphop <out_prefix>`
