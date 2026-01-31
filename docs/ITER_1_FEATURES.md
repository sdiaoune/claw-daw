# Iteration 1 (Pick 3) — Viral Day‑1 Agent Readiness

Selected features (from the "release in the wild" list):

1) **Formal headless automation contract**
2) **TUI UX polish (stable, parseable screens)**
3) **Agent cookbook + templates (deterministic, non‑AI)**

---

## 1) Formal headless automation contract

### Goal
Make `claw-daw --headless` reliable for other agents and CI.

### Deliverables
- `--headless` supports:
  - `--script <path>` with `include other.txt`
  - `--strict` (stop on first error, non‑zero exit)
  - `--dry-run` (parse/validate commands, no renders)
- `dump_state <path>` output is deterministic and includes derived fields:
  - `derived.song_length_ticks`
  - `derived.song_length_seconds`
  - `derived.song_bars_estimate`

### Tests
- Unit test: `include` works and preserves line order.
- Unit test: `dump_state` writes valid JSON with derived fields.

---

## 2) TUI UX polish

### Goal
Make the interactive curses UI usable and agent-friendly.

### Deliverables
- Stable screen layout with 2 main views:
  - **Tracks/Mixer** view
  - **Arrange** view (patterns + clips)
- Consistent keybinds:
  - `:` command mode
  - `?` help
  - `1` Tracks/Mixer view
  - `2` Arrange view
  - `Up/Down` select track
  - `Space` play/stop

### Tests
- Manual smoke test: launch TUI, create project, add track, create pattern, place clip, export mp3 via headless.

---

## 3) Agent cookbook + templates

### Goal
Make it easy for agents to generate cool results in <60 seconds, offline.

### Deliverables
- `docs/AGENT_COOKBOOK.md` with:
  - 3 sample scripts (hip hop, lo-fi, house)
  - common commands, PPQ/ticks cheat sheet
  - export recipes (`export_mp3 trim=60`)
- `templates/` folder containing runnable headless scripts:
  - `templates/hiphop_1min.txt`
  - `templates/lofi_1min.txt`
  - `templates/house_1min.txt`

### Tests
- Run each template headless and confirm mp3 is produced.

---

## Exit criteria (iteration 1)
- Headless scripts are deterministic and safe for automation.
- TUI has stable views and predictable keybinds.
- Templates produce shareable 60s mp3 outputs.
