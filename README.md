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
  - **Drum Kits v1 (role-based)**: `list_drum_kits`, `set_drum_kit <track> <kit>`, and `add_note_pat ... <pitch|role> ...`
  - **808 presets**: `set_808 <track> <preset>` + `set_glide` for portamento
- **Genre Packs v1** (from-scratch, deterministic): `claw-daw pack <trap|house|boom_bap> ...`
- **Stylepacks v1 (opt-in / explicit request)** (scored iteration + reports): `claw-daw stylepack <trap_2020s|boom_bap|house> ...`
- **Prompt → script helper** (offline): style-aware scaffolding with **novelty control** (`--max-similarity`)
  - Supported styles: `hiphop | lofi | house | techno | ambient | trap | boom_bap`
- **MIDI out**: play to hardware/virtual MIDI ports (`claw-daw play`)

## Install

### Linux (recommended)
```bash
curl -fsSL https://www.clawdaw.com/install.sh -o /tmp/clawdaw-install.sh
bash /tmp/clawdaw-install.sh
```

### macOS
```bash
curl -fsSL https://www.clawdaw.com/install_mac.sh -o /tmp/clawdaw-install.sh
bash /tmp/clawdaw-install.sh
```

### Windows (PowerShell)
```powershell
iwr https://www.clawdaw.com/install_win.ps1 -UseBasicParsing -OutFile $env:TEMP\clawdaw-install.ps1
& $env:TEMP\clawdaw-install.ps1
```
Run in Administrator PowerShell to install system deps (Chocolatey).

Manual (Ubuntu):
```bash
sudo apt-get update
sudo apt-get install -y fluidsynth ffmpeg fluid-soundfont-gm pipx
pipx install claw-daw
```
If `claw-daw` is not found after install, run `pipx ensurepath` and restart your terminal.

### Verify install
```bash
claw-daw --version
claw-daw doctor
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
set_drum_kit 0 trap_hard

add_track 808 0
set_808 1 dist
set_glide 1 0:0:90

new_pattern 0 d1 2:0
add_note_pat 0 d1 kick 0:0 0:0:180 112
add_note_pat 0 d1 snare 0:2 0:0:180 108
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
- `docs/AGENT_PLAYBOOK.md`
- `docs/ARCH_STYLEPACK_PIPELINE.md` (prompt → BeatSpec → compile → render → score → iterate)

## Notes / guarantees

- 100% offline core (no network APIs).
- Reproducibility depends on pinning: claw-daw version + SoundFont + seed/script.
- Project format is JSON (current schema v7; migrations included).

## License

MIT
