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
