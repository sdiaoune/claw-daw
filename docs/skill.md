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
  --script tools/my_song.txt
```

## One-shot features (agent-first)

When a user prompts an agent, the agent can use claw-daw for fast “one-shot” generation and revisions:

- **Drum Kits v1 (role-based drums)**:
  - `list_drum_kits`
  - `set_drum_kit <track_index> <trap_hard|house_clean|boombap_dusty|gm_basic>`
  - `add_note_pat ... <pitch|role> ...` where role can be: `kick|snare|clap|hh|oh|rim|perc_low|perc_high|crash|fx` (aliases supported)
- **808 presets + glide**:
  - `set_808 <track_index> <preset>`
  - `set_glide <track_index> <ticks|bar:beat>`
- **Genre Packs v1** (from-scratch, no templates):
  - `claw-daw pack <trap|house|boom_bap> --out <name> --seed <n> --attempts <n> --max-similarity <0..1>`
- **Novelty control** for prompt→script iteration:
  - `claw-daw prompt ... --iters N --max-similarity 0.85–0.95`
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
