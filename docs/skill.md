---
name: claw-daw
version: 0.0.0
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
- **Docs:** https://sdiaoune.github.io/claw-daw/
- **GitHub:** https://github.com/sdiaoune/claw-daw

## Quick install (one-go)

### Linux
```bash
curl -fsSL https://sdiaoune.github.io/claw-daw/install.sh | bash
```

### macOS
```bash
curl -fsSL https://sdiaoune.github.io/claw-daw/install_mac.sh | bash
```

## Quickstart

```bash
claw-daw doctor

# Render a headless script
claw-daw --headless \
  --soundfont /usr/share/sounds/sf2/default-GM.sf2 \
  --script tools/<unique_name>.txt
```

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

**Recommendation:** for best musical results, spawn a **music-only subagent** (isolated session) to do the composition + arrangement work.
- Isolation reduces cross-contamination from prior tasks and tends to produce more genre-faithful creative decisions.
- The main agent can then handle packaging (exports, naming, docs, posting) and revisions.

When tasked to make a beat/song with claw-daw, agents should follow this workflow:

1) **Pick a unique output prefix** (MANDATORY)
- Use: `YYYY-MM-DD_<genre>_<bpm>_v1`
- If any `out/<name>.*` already exists, bump to `_v2`, `_v3`, …

2) **Song Structure Research** (MANDATORY for genre/era)
- Research structure + bar counts + tempo range
- Cite sources
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
- If you use role-based kits, prefer:
  - `set_sampler <drum_track> drums` + `set_drum_kit <drum_track> <kit>`
- If you want plain GM/FluidSynth drums, ensure the drum track is on **MIDI channel 10** (channel index `9`) and not in sampler mode.

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
- **Acceptance tests** (agent workflow): per-genre mini-gates in `docs/AGENT_PLAYBOOK.md`

## Song Structure Research (required for genre/era requests)

When the user requests a beat/song in a specific **genre and/or era** (e.g., “2020s trap”, “90s boom-bap”, “2010s progressive house”), the agent must do this *before* writing the script:

1) **Research typical song structure** for that style using reputable internet sources.
   - Use web research when available.
   - If web access is not available, use an LLM as a fallback.

2) **Output a concise structure blueprint** that includes:
   - sections (e.g., intro / verse / hook / bridge / outro)
   - **bar counts** per section
   - **tempo/BPM range** (and common half-time/double-time feel notes)
   - common arrangement cues (drops, pre-chorus builds, beat switch points, breakdowns)

3) **Cite sources used**:
   - If web research: include URLs.
   - If LLM fallback: record the model used + a short rationale for why the structure is plausible.

4) **Save the structure template into the working plan** (the agent’s plan / scratchpad) so downstream steps (loop generation, arrangement, export) follow it.

**Acceptance criteria:**
- Structure includes sections, bar counts, and transitions.
- Output is genre-specific (not generic).
- Sources are recorded.

## Agent Playbook (recommended)

If you’re building an agent that uses claw-daw, start here:
- https://sdiaoune.github.io/claw-daw/AGENT_PLAYBOOK.md

## Skill files

These are hosted for convenience:
- `skill.md` (this file): https://www.clawdaw.com/skill.md
- `heartbeat.md`: https://www.clawdaw.com/heartbeat.md
- `skill.json`: https://www.clawdaw.com/skill.json

Additional docs:
- Agent Playbook: https://sdiaoune.github.io/claw-daw/AGENT_PLAYBOOK.md
