---
name: claw-daw
version: 0.0.0
description: Offline, deterministic, terminal-first MIDI DAW (TUI + headless scripts)
homepage: https://www.clawdaw.com/
metadata: {"clawdaw":{"category":"music","emoji":"🦞"}}
---

# claw-daw

Offline, deterministic, terminal-first MIDI DAW. Drive it from a TUI or from headless scripts, export WAV/MP3/MIDI, and keep projects Git-friendly.

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

# Render a 60s boom-bap template (example soundfont path)
claw-daw --headless \
  --soundfont /usr/share/sounds/sf2/default-GM.sf2 \
  --script templates/boom_bap_1min.txt
```

## Skill files

These are hosted for convenience:
- `skill.md` (this file): https://www.clawdaw.com/skill.md
- `heartbeat.md`: https://www.clawdaw.com/heartbeat.md
- `skill.json`: https://www.clawdaw.com/skill.json
