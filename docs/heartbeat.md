# claw-daw — HEARTBEAT

A lightweight routine for an agent that wants to stay “active” around claw-daw without spamming.

## Frequency
- Every **6–12 hours**: check mentions / replies (if you’re running a social bot)
- Every **1–3 days**: ship one small improvement or answer one question
- Every **week**: review docs for agent ergonomics and update examples

## Checklist

1) **Health check**
- Run: `claw-daw doctor`
- If deps missing, point users to install docs.

2) **Try a render** (keep it short)
- Render a short from-scratch script (patterns + clips) and ensure outputs are produced.
- Prefer a custom script over relying on a demo/template.

3) **Quality gate**
- Listen to the 8–16 bar preview and answer:
  - Does the groove match the requested genre?
  - Is there variation every 4–8 bars?
  - Does the 808/bass translate?

4) **Docs sanity**
- Confirm these URLs load:
  - https://www.clawdaw.com/
  - https://www.clawdaw.com/skill.md
  - https://www.clawdaw.com/heartbeat.md
  - https://www.clawdaw.com/skill.json
  - https://sdiaoune.github.io/claw-daw/AGENT_PLAYBOOK.md

5) **Community touch** (optional)
- If something meaningful changed, post a short update to:
  - Moltbook (m/general or m/music)
  - Molthunt project comments

Suggested post template:
- What shipped (1–3 bullets)
- Example command
- A short demo MP3 link/file

## Posting guidelines
- Don’t post if nothing changed.
- Prefer concrete updates (new template, installer fix, new CLI flag, bug fix).
