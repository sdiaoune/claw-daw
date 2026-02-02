# claw-daw

Offline, deterministic, terminal-first MIDI DAW.

**Think “DAW for agents”:** you (or an agent) write a small headless script (patterns + clips), render, listen, tweak, rerender — and keep everything diffable in Git.

- Homepage: https://www.clawdaw.com/
- Docs: https://sdiaoune.github.io/claw-daw/
- GitHub: https://github.com/sdiaoune/claw-daw

## What you can do

- **Headless scripting**: build songs with `new_project / add_track / new_pattern / add_note_pat / place_pattern / export_*`
- **Deterministic output**: same script + same seed + same version + same SoundFont → same render
- **Exports**: `WAV / MP3 / M4A / MIDI` + project `JSON`
- **Agent ergonomics**:
  - bar:beat timecodes (`2:0`, `1:3:120`)
  - note expressions (`chance`, `accent`, `mute`, `glide_ticks`)
  - select/apply edits (`select_notes`, `apply_selected`)
  - validate/diff/analyze helpers
- **Sampler** (offline): built-in `drums` + `808`
  - **Drum Kits**: `set_kit <track> <preset>` (agent-friendly kit selection)
  - **808 presets**: `set_808 <track> <preset>` + `set_glide` for portamento
- **Prompt → script helper** (offline): style-aware scaffolding with **novelty control** (`--max-similarity`)
  - Supported styles behave like **Genre Packs**: `hiphop | lofi | house | techno | ambient`
- **MIDI out**: play to hardware/virtual MIDI ports (`claw-daw play`)

## Install

### Linux (recommended)
```bash
curl -fsSL https://sdiaoune.github.io/claw-daw/install.sh | bash
```

### macOS
```bash
curl -fsSL https://sdiaoune.github.io/claw-daw/install_mac.sh | bash
```

Manual (Ubuntu):
```bash
sudo apt-get update
sudo apt-get install -y fluidsynth ffmpeg fluid-soundfont-gm pipx
pipx reinstall "git+https://github.com/sdiaoune/claw-daw.git"
```

## Quickstart

### 1) Health check + SoundFont
```bash
claw-daw doctor
claw-daw paths --soundfont
```

### 2) Render a headless script (recommended workflow)
```bash
claw-daw --headless \
  --soundfont /usr/share/sounds/sf2/default-GM.sf2 \
  --script tools/my_song.txt
```

### 3) Prompt → script helper (optional)
This is a scaffolding tool. Best results come from iterating like a producer.

```bash
SF2=$(claw-daw paths --soundfont | head -n 1)
claw-daw --soundfont "$SF2" prompt \
  --out my_prompt_song \
  --prompt "modern trap, 140bpm, E minor, spacey" \
  --iters 8 --max-similarity 0.85 \
  --render --preview-bars 8

# outputs:
# tools/my_prompt_song.txt
# out/my_prompt_song.preview.mp3
# out/my_prompt_song.mp3
# out/my_prompt_song.mid
# out/my_prompt_song.json
```

## Minimal script example (from scratch)

```txt
new_project minimal_demo 140
set_swing 16

add_track Drums 0
set_kit 0 tight

add_track 808 0
set_808 1 dist
set_glide 1 0:0:90

new_pattern 0 d1 2:0
add_note_pat 0 d1 36 0:0 0:0:180 112
add_note_pat 0 d1 38 0:2 0:0:180 108
place_pattern 0 d1 0:0 16

# (optional) a single bar bass pickup
new_pattern 1 b1 1:0
add_note_pat 1 b1 33 0:2 0:1:0 112
place_pattern 1 b1 0:0 16

save_project out/minimal_demo.json
export_midi out/minimal_demo.mid
export_mp3 out/minimal_demo.mp3 preset=clean
```

## MIDI out (hardware / virtual ports)
```bash
claw-daw midi-ports
claw-daw play out/minimal_demo.json --midi-out "YOUR PORT NAME"
```

## Docs

- `docs/USER_GUIDE.md`
- `docs/AGENT_COOKBOOK.md`
- `docs/TROUBLESHOOTING.md`

## Notes / guarantees

- 100% offline core (no network APIs).
- Reproducibility depends on pinning: claw-daw version + SoundFont + seed/script.
- Project format is JSON (current schema v6; migrations included).

## License

MIT
