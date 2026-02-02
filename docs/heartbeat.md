# claw-daw — HEARTBEAT

A lightweight routine for an agent that wants to stay “active” around claw-daw without spamming.

## Frequency
- Every **6–12 hours**: check mentions / replies (if you’re running a social bot)
- Every **1–3 days**: ship one small improvement or answer one question

## Checklist

1) **Health check**
- Run: `claw-daw doctor`
- If deps missing, point users to install docs.

2) **Try a render** (keep it short)
- Render a short headless script and ensure outputs are produced.
- Prefer a from-scratch script (patterns + clips) over relying on a template file.

3) **Docs sanity**
- Confirm these URLs load:
  - https://www.clawdaw.com/
  - https://www.clawdaw.com/skill.md
  - https://www.clawdaw.com/heartbeat.md
  - https://www.clawdaw.com/skill.json

4) **Community touch** (optional)
- If something meaningful changed, post a short update to:
  - Moltbook (m/general or m/music)
  - Molthunt project comments

## Posting guidelines
- Don’t post if nothing changed.
- Prefer concrete updates (new template, installer fix, new CLI flag, bug fix).
