---
name: claw-daw
version: 0.2.2
description: Offline, deterministic, terminal-first MIDI DAW (TUI + headless scripts)
homepage: https://www.clawdaw.com/
metadata: {"clawdaw":{"category":"music","emoji":"🦞"}}
---

# claw-daw

Offline, deterministic, terminal-first MIDI DAW. Drive it from a TUI or from headless scripts, export WAV/MP3/MIDI, and keep projects Git-friendly.

**Important:** claw-daw is the workstation.
When a user prompts an agent, the agent should use claw-daw like a producer uses a DAW: write/edit scripts, iterate on arrangement/groove/sound choices, and export artifacts.
The user is prompting the *agent*, not claw-daw.

- **Homepage:** https://www.clawdaw.com/
- **Docs:** https://www.clawdaw.com/USER_GUIDE.md
- **GitHub:** https://github.com/sdiaoune/claw-daw

## Skill Changelog

### Unreleased
- Clean exports are now the default for prompt, pack, stylepack, headless preview, and package export paths.
- Added audio sanity gates to the quality workflow so preview and master renders fail closed on obvious hiss, rumble, DC offset, and clipped/transient artifacts.
- Tightened guidance for avoiding broadband noise, clicks/pops, harsh transients, aliasing-like whine, low-end rumble, hanging notes, and unintended tails.

### 0.2.1 (2026-02-06)
- Synced quality workflow guidance with repo refactor (`claw-daw quality ...`).
- Updated `export_package` examples to use `<name>` prefix form.
- Added gated render guidance for `claw-daw pack ... --render`.
- Updated stylepack flow wording to include gated final export.

## Quick install (one-go)

### Linux
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
If `claw-daw` is not found after install, run `pipx ensurepath` and restart your terminal.

## Quickstart

```bash
claw-daw --version
claw-daw doctor
claw-daw paths --soundfont

# Render a headless script
claw-daw --headless \
  --soundfont /path/to/your.sf2 \
  --script tools/<unique_name>.txt
```
Tip: set `CLAW_DAW_SOUNDFONT=/path/to/your.sf2` to make renders less verbose.

## Output naming / overwrite prevention (MANDATORY)

claw-daw exports are file-based. If you reuse the same `<name>` / `--out` prefix, you will overwrite:
- `out/<name>.mp3`
- `out/<name>.mid`
- `out/<name>.json`
- `out/<name>.report.json` (stylepacks)

**Rule:** every new beat/song must use a **unique output prefix**.

**Recommended naming convention:**
- `<yyyy-mm-dd>_<genre>_<bpm>_v<nn>` (example: `2026-02-02_trap_150_v1`)

**When revising the same song:** increment the version (`_v2`, `_v3`) and keep prior files.

**Agent requirement:** before rendering, the agent must check whether any of these files already exist for the chosen prefix and, if so, pick a new prefix (or ask the user).

## Agent-first workflow (what to do, every time)

When tasked to make a beat/song with claw-daw, agents should follow this workflow.

**Best practice (recommended):** for best musical results, spawn **music-only subagents** (isolated sessions) and run them in a pipeline.
If your environment does not support subagents, proceed as a single agent and follow the same steps.

### Recommended subagent roles (use these titles)

1) **A&R / Reference Agent**
- Clarifies genre lane + era, BPM/key, mood, 2–3 reference *vibes* (describe only).
- Outputs: creative brief + bar-based section map.

2) **Drum & Perc Agent**
- Programs the signature groove + 2 variations + fills (every 8 bars), with swing/microtiming notes.
- Uses **supported drum roles** only.

3) **Harmony & Bass Agent**
- Writes chord loop + bouncy bassline (+ turnaround variation).
- Avoids bass pitfalls (no `drum_kit` on melodic tracks; minimal bass reverb).

4) **Melody / Lead Agent**
- Writes a sparse, catchy motif + call/response fills that stay out of the vocal pocket.

5) **Arrangement Agent**
- Builds the full song (2:30–3:10) from sections; adds drops, risers/impacts, and energy changes.

6) **Mix / Polish Agent**
- Gain stages + basic FX balance; exports master + stems; ensures drums/bass translate.

- Isolation reduces cross-contamination from prior tasks and tends to produce more genre-faithful creative decisions.
- The main agent coordinates handoffs (files + constraints) and handles packaging (exports, naming, docs/posting) + revisions.

When tasked to make a beat/song with claw-daw, agents should follow this workflow:

1) **Pick a unique output prefix** (MANDATORY)
- Use: `YYYY-MM-DD_<genre>_<bpm>_v1`
- If any `out/<name>.*` already exists, bump to `_v2`, `_v3`, …

2) **Song Structure Research** (MANDATORY for genre/era)
- Research structure + bar counts + tempo range
- Cite sources (or explicitly note when web access is unavailable)
- Save the blueprint into the working plan

3) **Generate a solid v1 quickly (choose one path)**
- **From scratch (DEFAULT / full artistic freedom):**
  - write `tools/<name>.txt` with patterns + clips
- **Genre pack (ONLY if explicitly requested):**
  - `claw-daw pack <trap|house|boom_bap> --out <name> [--seed <n>] --attempts 6`
- **Stylepack (ONLY if explicitly requested):**
  - Use when the user explicitly asks for “stylepack”, “scored iteration”, or `out/<name>.report.json`.
  - `claw-daw stylepack <trap_2020s|boom_bap|house> --out <name> --soundfont <sf2> [--seed <n>] --attempts 6`

Seed behavior for generators:
- Omit `--seed` on `claw-daw prompt`, `claw-daw pack`, or `claw-daw stylepack` to auto-pick a fresh seed for that run.
- Pass `--seed <n>` to replay the same generation deterministically.

4) **Apply palette + groove macros (recommended quality lift)**
- `apply_palette <style>` to set better GM programs + mixer defaults per role
- `gen_drum_macros <track> <base_pattern> ...` to create 4/8-bar variations + fills
- `gen_bass_follow <track> <pattern> <length> roots=...` to lock bass/808 to harmony
- `arrange-spec <spec.yaml> ...` to place sections + dropouts/fills deterministically

5) **Render + export deliverables**
- Always export: MP3 + MIDI + JSON
- If using stylepacks: ensure `out/<name>.report.json` is produced

6) **Mix + QA (MANDATORY, streaming default)**
- Prepare buses + mix spec: `python3 tools/mix_prepare.py out/<name>.json --preset edm_streaming --mix-out tools/<name>.mix.json`
- Optional section energy: `python3 tools/section_gain.py out/<name>.json`
- Validate mix spec: `python3 tools/mix_spec_validate.py out/<name>.json tools/<name>.mix.json`
- Preview gate: `python3 tools/preview_gate.py out/<name>.json tools/<name>.mix.json <name> --preset edm_streaming`
- Full export + metering: `export_package <name> preset=clean mix=tools/<name>.mix.json stems=1 busses=1 meter=1`
- Master gate: `python3 tools/mix_gate.py out/<name>.meter.json --preset edm_streaming`
- Stem gate: `python3 tools/mix_gate_stems.py out/<name>_stems --bus-dir out/<name>_busses --preset edm_streaming --lufs-guidance`
- Audio sanity QA: `claw-daw doctor --audio out/<name>.mp3`
- One-shot equivalent (repo CLI): `claw-daw quality out/<name>.json --out <name> --preset edm_streaming --section-gain`

7) **Quality gates before sending**
- Check: genre acceptance tests + avoid overwriting + listen to preview
- Reject the render if you hear or measure any of these unless the brief explicitly asks for texture:
  - broadband hiss / white-noise or pink-noise-like beds
  - clicks, pops, crackle, clipping, digital distortion
  - harsh transients, zipper noise, metallic aliasing/whine
  - DC offset, sub rumble, hanging notes, or unintended reverb/delay tails

---

## One-shot features (agent-first)

When a user prompts an agent, the agent can use claw-daw for fast “one-shot” generation and revisions:

- **Drum Kits v1 (role-based drums)**:
  - `list_drum_kits`
  - `set_drum_kit <track_index> <trap_hard|house_clean|boombap_dusty|gm_basic>`
  - `add_note_pat ... <pitch|role> ...` where role can be:
    - `kick|snare|clap|rim|hh|oh|ph|tom_low|tom_mid|tom_high|crash|ride|perc|shaker`
    - (`hh/oh/ph` are aliases for `hat_closed/hat_open/hat_pedal`)
- **Native instrument plugins (offline render-only)**:
  - `list_instruments`
  - `set_instrument <track_index> <instrument_id> preset=<name> seed=<n> <param>=<value>...`
- **Sample packs (WAV drum one-shots)**:
  - `scan_sample_pack <path> id=<pack_id> include=*.wav`
  - `list_sample_packs`
  - `set_sample_pack <track_index> <pack_id|path> seed=<n> gain_db=<db>`
  - `convert_sample_pack_to_sf2 <pack_id|path> <out.sf2> tool=sfz2sf2`

### Drum rendering sanity checklist (prevents “crackling / not-drums” failures)

If drums sound like crackling/noise or “not drums”, it’s almost always one of these:

1) **Unsupported drum roles**
- Only use the supported roles above. Avoid ad-hoc roles like `perc_low` / `perc_high`.
- If you need more percussion, use `perc`, `shaker`, or `tom_*`.

2) **Wrong render mode for drums (sampler vs GM drum channel)**
- **Default for reliable exports:** render drums as **plain GM drums on MIDI channel 10** (channel index `9`).
- Sampler drums (`set_sampler <drum_track> drums` + `set_drum_kit ...`) are **opt-in** and may crackle on some setups.
- The renderer now defaults to a safe path (converts sampler drums → GM channel 10) unless you explicitly opt in to sampler drums.

3) **Always do a 0–10s preview before exporting stems**
- Render a short preview (`export_preview_mp3`) and listen specifically for: kick/snare clarity + hats not crackling.

### Clean render policy (default unless explicitly requested)

Agents should assume the user wants a clean export unless they explicitly ask for `lofi`, hiss, vinyl, tape, dusty noise, crackle, grit, saturation-heavy textures, or other intentional artifacts.

- Default mastering/export path: `preset=clean`
- Default preview path: clean preview first, then add texture only if the brief calls for it
- Noise-heavy instruments and presets are opt-in. If you choose a texture preset, mention it in the changelog/notes
- Do not add reverb/delay tails to kick or bass
- Do not leave long tails, hanging notes, or clipped render boundaries in final deliverables

### Clean export acceptance criteria

Before sending a beat/song, the agent should be able to say all of these are true:

- Preview gate passed
- Master gate passed
- Stem/bus gate passed
- `claw-daw doctor --audio out/<name>.mp3` shows no serious mix sanity warnings
- No audible broadband hiss, white noise, pink-noise bed, crackle, clicks, pops, clipping, or digital breakup unless explicitly requested
- No obvious low-end rumble, DC offset, zipper noise, or metallic aliasing-like whine
- No hanging notes or unintended reverb/delay tails after the musical ending
- Kick, snare, hats, and bass all sound intentional and distinct in the first 10 seconds

### Bass rendering sanity checklist (prevents “bass present in MIDI but inaudible” failures)

If bass notes exist but you can’t hear bass, check:

1) **No `drum_kit` on melodic tracks**
- `drum_kit` is for role-based drum mapping. Don’t set it on bass/keys/lead tracks.

2) **Pick a bass patch that translates on small speakers**
- Prefer GM synth bass patches (e.g. `synth_bass_1`) or layer some mid harmonics.

3) **Keep bass FX minimal**
- Avoid reverb on bass; keep it mostly mono/center.

4) **Preview the low-end early**
- Before stems/final export: listen to the first 10–20 seconds on small speakers/headphones.

- **808 presets + glide**:
  - `set_808 <track_index> <preset>`
  - `set_glide <track_index> <ticks|bar:beat>`
- **Genre Packs v1** (from-scratch, no templates):
  - script only: `claw-daw pack <trap|house|boom_bap> --out <name> [--seed <n>] --attempts <n> --max-similarity <0..1>`
  - gated render: `claw-daw pack <trap|house|boom_bap> --out <name> [--seed <n>] --attempts <n> --max-similarity <0..1> --render --soundfont <sf2> --quality-preset edm_streaming --section-gain`
- **Novelty control** for prompt→script iteration:
  - `claw-daw prompt ... [--seed <n>] --iters N --max-similarity 0.85–0.95`
- **Stylepacks v1 (opt-in / explicit request)**: BeatSpec → compile → score → iterate → gated export → report
  - `claw-daw stylepack <trap_2020s|boom_bap|house> --out <name> --soundfont <sf2> [--seed <n>] --attempts 6 --score-threshold 0.60`
  - writes `out/<name>.report.json`
- **Mix sanity gate (audio-level)** is included in stylepacks scoring and will retry deterministically when it detects obvious issues.
- **Sound engineering (MANDATORY for agents)**:
  - `export_package <name> preset=clean mix=tools/<name>.mix.json stems=1 busses=1 meter=1`
  - Presets + gates: `tools/mix_presets.json`, `tools/mix_gate.py`, `tools/mix_gate_stems.py`
- **Metering (post-export QA)**:
  - `meter_audio out/<name>.mp3 out/<name>.meter.json` (LUFS integrated+short-term, true-peak, crest/DC offset, stereo correlation+balance, spectral tilt)
- **Artifact QA (post-export QA)**:
  - `claw-daw doctor --audio out/<name>.mp3` (adds mix sanity warnings for hiss, rumble, hot/clipped transients, and DC offset)
- **Bus stems (quick deliverables)**:
  - `export_busses out/busses_<name>`
- **Drum variations + fills macro**:
  - `gen_drum_macros <track> <base_pattern> out_prefix=drums seed=0 make=both|4|8`
- **Bass follower**:
  - `gen_bass_follow <track> <pattern> <length> roots=... seed=... gap_prob=... glide_prob=...`
- **Palette presets**:
  - `apply_palette <style> [mood=...]` (uses track names to infer roles)
- **Section-aware arrangement compiler**:
  - `claw-daw arrange-spec <spec.yaml> --in <project.json> --out <project_out.json>`
- **Acceptance tests** (agent workflow): per-genre mini-gates in https://www.clawdaw.com/AGENT_PLAYBOOK.md
- **Quality workflow command:** `claw-daw quality out/<name>.json --out <name> --preset edm_streaming --section-gain`

## Song Structure Research (required for genre/era requests)

When the user requests a beat/song in a specific **genre and/or era** (e.g., “2020s trap”, “90s boom-bap”, “2010s progressive house”), the agent must do this *before* writing the script:

1) **Research typical song structure** for that style using reputable internet sources.
   - Use web research when available.
   - If web access is not available, use an LLM/heuristics as a fallback and explicitly note the lack of sources.

2) **Output a concise structure blueprint** that includes:
   - sections (e.g., intro / verse / hook / bridge / outro)
   - **bar counts** per section
   - **tempo/BPM range** (and common half-time/double-time feel notes)
   - common arrangement cues (drops, pre-chorus builds, beat switch points, breakdowns)

3) **Cite sources used**:
   - If web research: include URLs.
   - If web access is unavailable: explicitly state that and provide a short rationale for why the structure is plausible.

4) **Save the structure template into the working plan** (the agent’s plan / scratchpad) so downstream steps (loop generation, arrangement, export) follow it.

**Acceptance criteria:**
- Structure includes sections, bar counts, and transitions.
- Output is genre-specific (not generic).
- Sources are recorded.

## Agent Playbook (recommended)

If you’re building an agent that uses claw-daw, start here:
- https://www.clawdaw.com/AGENT_PLAYBOOK.md

## Skill files

These are hosted for convenience:
- `skill.md` (this file): https://www.clawdaw.com/skill.md
- `heartbeat.md`: https://www.clawdaw.com/heartbeat.md
- `skill.json`: https://www.clawdaw.com/skill.json

Additional docs:
- Agent Playbook: https://www.clawdaw.com/AGENT_PLAYBOOK.md
