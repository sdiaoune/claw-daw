---
name: claw-daw
version: 0.2.0
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
- **Stylepack (best default, includes scoring + report):**
  - `claw-daw stylepack <trap_2020s|boom_bap|house> --out <name> --soundfont <sf2> --attempts 6`
- **Genre pack (fast scaffolding):**
  - `claw-daw pack <trap|house|boom_bap> --out <name> --seed <n> --attempts 6`
- **From scratch (manual script):**
  - write `tools/<name>.txt` with patterns + clips

4) **Apply palette + groove macros (recommended quality lift)**
- `apply_palette <style>` to set better GM programs + mixer defaults per role
- `gen_drum_macros <track> <base_pattern> ...` to create 4/8-bar variations + fills
- `gen_bass_follow <track> <pattern> <length> roots=...` to lock bass/808 to harmony
- `arrange-spec <spec.yaml> ...` to place sections + dropouts/fills deterministically

5) **Render + export deliverables**
- Always export: MP3 + MIDI + JSON
- If using stylepacks: ensure `out/<name>.report.json` is produced

6) **Quality gates before sending**
- Check: genre acceptance tests + avoid overwriting + listen to preview

---

## One-shot features (agent-first)

When a user prompts an agent, the agent can use claw-daw for fast “one-shot” generation and revisions:

- **Drum Kits v1 (role-based drums)**:
  - `list_drum_kits`
  - `set_drum_kit <track_index> <trap_hard|house_clean|boombap_dusty|gm_basic>`
  - `add_note_pat ... <pitch|role> ...` where role can be:
    - `kick|snare|clap|rim|hh|oh|ph|tom_low|tom_mid|tom_high|crash|ride|perc|shaker`
    - (`hh/oh/ph` are aliases for `hat_closed/hat_open/hat_pedal`)

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
  - `claw-daw pack <trap|house|boom_bap> --out <name> --seed <n> --attempts <n> --max-similarity <0..1>`
- **Novelty control** for prompt→script iteration:
  - `claw-daw prompt ... --iters N --max-similarity 0.85–0.95`
- **Stylepacks v1 (best default for agents)**: BeatSpec → compile → render → score → iterate → report
  - `claw-daw stylepack <trap_2020s|boom_bap|house> --out <name> --soundfont <sf2> --attempts 6 --score-threshold 0.60`
  - writes `out/<name>.report.json`
- **Mix sanity gate (audio-level)** is included in stylepacks scoring and will retry deterministically when it detects obvious issues.
- **Drum variations + fills macro**:
  - `gen_drum_macros <track> <base_pattern> out_prefix=drums seed=0 make=both|4|8`
- **Bass follower**:
  - `gen_bass_follow <track> <pattern> <length> roots=... seed=... gap_prob=... glide_prob=...`
- **Palette presets**:
  - `apply_palette <style> [mood=...]` (uses track names to infer roles)
- **Section-aware arrangement compiler**:
  - `claw-daw arrange-spec <spec.yaml> --in <project.json> --out <project_out.json>`
- **Acceptance tests** (agent workflow): per-genre mini-gates in https://www.clawdaw.com/AGENT_PLAYBOOK.md

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
