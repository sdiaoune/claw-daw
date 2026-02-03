# Agent Cookbook — claw-daw

claw-daw is an offline, deterministic, terminal-first MIDI DAW that agents can drive via **headless scripts**.

If you want the “how to be a good music-producing agent” workflow + checklists, start here:
- `docs/AGENT_PLAYBOOK.md`

---

## The 5 agent-first features (cheat sheet)

1) **Drum Kits (role-based drums)**
```txt
set_sampler 0 drums
set_drum_kit 0 trap_hard
add_note_pat 0 d1 kick  0:0 0:0:120 112
add_note_pat 0 d1 snare 0:2 0:0:120 108
```

2) **808 presets + glide**
```txt
set_sampler 1 808
set_808 1 dist
set_glide 1 0:0:90
```

3) **Genre Packs (from-scratch generation)**
```bash
claw-daw pack trap --out 2026-02-03_trap_140_v1 --seed 7 --attempts 6 --max-similarity 0.9 --render
# tools/2026-02-03_trap_140_v1.txt
# out/2026-02-03_trap_140_v1.{mp3,mid,json}
```

4) **Novelty control (prompt→script iteration)**
```bash
claw-daw prompt --out ideas_v1 \
  --prompt "dark lofi, 78bpm, Rhodes, dusty drums" \
  --iters 6 --max-similarity 0.88 --seed 3
```

5) **Acceptance tests (quality gates)**
- See `docs/AGENT_PLAYBOOK.md#9-acceptance-tests-per-genre-mini-gates`

---

## Quick start

```bash
claw-daw --headless \
  --soundfont /usr/share/sounds/sf2/default-GM.sf2 \
  --script templates/hiphop_1min.txt
```

---

## Minimal agent loop (recommended)

1) Pick a **unique output prefix** (to avoid overwriting): `YYYY-MM-DD_<genre>_<bpm>_v1`
2) Write `tools/<name>.txt`
3) Render:

```bash
claw-daw --headless --soundfont <SF2> --script tools/<name>.txt
```

4) Iterate by editing the script and rerendering to a **new version** (`_v2`, `_v3`, …).

---

## Optional: claw-daw prompt (helper, not a replacement)

claw-daw includes an **offline prompt→script helper** for quick scaffolding. It’s best treated as a starting point, not the final result.

Key features for one-shot agent workflows:
- **Style presets**: the prompt parser infers a `style` and applies defaults (BPM, swing, drum density, mastering preset).
- **Novelty control**: iterate while keeping attempts “different enough” using similarity scoring.

```bash
claw-daw prompt --out prompt_v1 \
  --prompt "lofi, dusty, 82bpm, Rhodes chords, soft hats" \
  --seed 7 --iters 6 --max-similarity 0.88
# tools/prompt_v1.txt
```

Notes:
- Lower `--max-similarity` ⇒ stronger novelty requirement.
- For deterministic A/B tests, keep `--seed` fixed and only change one constraint at a time.

---

## Time model (ticks / PPQ)

- Default `PPQ=480`
- `1 beat (quarter note) = 480 ticks`
- In 4/4: `1 bar = 4 beats = 1920 ticks`
- 16ths: `PPQ/4 = 120 ticks`

Practical conversions (4/4):
- `bar_ticks = ppq*4`
- `beat_ticks = ppq`
- `sixteenth_ticks = ppq//4`

---

## Swing semantics

`set_swing <0-75>` applies swing by delaying **odd 16th steps** (offbeat 16ths).
- `0` = straight
- `15–30` = typical hiphop/lofi feel

Swing is applied during MIDI rendering (export/playback), not by permanently rewriting notes.

---

## Loop vs render region

- `set_loop a b` / `clear_loop`
  - primarily for **playback looping**
  - takes precedence over render region in headless exports

- `set_render_region a b` / `clear_render_region`
  - defines an explicit export window `[a,b)` in ticks
  - useful for "render only bars 8–16" workflows

If neither is set, exports render the whole song up to the derived end tick.

---

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

---

## Determinism guidelines

For shareable, repeatable outputs:
- Prefer patterns + clips (avoid long linear note lists)
- Use deterministic generators (`gen_drums ... seed=N`) when you generate
- Pin version + SoundFont path for strict reproducibility

---

## Common workflow (agent)

1) Create project + tracks
2) Create 1–2 bar patterns (drums/bass/keys)
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

---

## Drum Kits + drum generation

### Drum Kits (sampler)
Agent-friendly abstractions:
- `set_kit <track_index> <preset>` — selects built-in drums sampler preset
- `set_808 <track_index> <preset>` — selects built-in 808 sampler preset
- `set_glide <track_index> <ticks|bar:beat>` — portamento for the 808 sampler

### Drum kits (role → MIDI mapping)
Choose a deterministic drum kit mapping so you can write role names:
- `set_drum_kit <track_index> <trap_hard|house_clean|boombap_dusty|gm_basic>`
- `list_drum_kits`

Example:
```txt
add_track Drums 0
set_sampler 0 drums
set_drum_kit 0 trap_hard
new_pattern 0 d 2:0
add_note_pat 0 d kick  0:0 0:0:180 115
add_note_pat 0 d snare 0:2 0:0:150  98
```

### Drum generation utility

`gen_drums <track> <pattern> <length_ticks> <style> seed=0 density=0.8`

`gen_drum_macros <track> <base_pattern> out_prefix=dr seed=0 make=both|4|8` (variations + fills)

- `style`: `hiphop|lofi|house`
- deterministic (`seed`)
- writes kick/snare/hats pattern using 16th grid

---

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

---

## Agent-native utilities (lint/diff/validation)

These commands are designed for automated workflows:

- `analyze_refs <out.json>` — detect missing pattern references / unused patterns
- `validate_project` — best-effort clamp/migrate in-memory project
- `diff_projects <a.json> <b.json> <out.diff>` — produce a unified diff
