# Iteration 2 (Pick 3) — TUI Launch Polish

Selected features:

1) **TUI stable views + keybind stability**
2) **Headless error reporting / diagnostics (line numbers, dry-run report)**
3) **One-command demo render (render_demo) + deterministic outputs**

---

## 1) TUI stable views + keybind stability

### Goal
Make the curses UI genuinely usable for humans and predictable for agents.

### Deliverables
- Two fixed views:
  - View 1: **Tracks/Mixer** (tracks list + mixer params)
  - View 2: **Arrange** (patterns list + clips list for selected track)
- Keybinds:
  - `1` tracks/mixer view
  - `2` arrange view
  - `:` command mode
  - `?` help
  - `Up/Down` select track
  - `Space` play/stop
  - `q` quit
- Show selected track index in header.

### Tests
- Manual: create project, add track, create pattern, place clip, export.

---

## 2) Headless error reporting / diagnostics

### Goal
Agents need actionable error messages.

### Deliverables
- `--strict` prints failing line + command
- `--dry-run` prints summary (commands executed, warnings)
- `include` failures show full resolved path

### Tests
- Unit test: strict mode raises on unknown command
- Unit test: include missing file raises

---

## 3) One-command demo render (render_demo)

### Goal
A viral one-liner for agents to get output.

### Deliverables
- Headless command: `render_demo <style> <out_prefix>`
  - styles: hiphop|lofi|house
  - writes `<out_prefix>.mp3` and `<out_prefix>.json` and `<out_prefix>.mid`
- Deterministic (same input = same output)

### Tests
- Run render_demo for each style and verify files exist.

---

## Exit criteria
- TUI looks sane and consistent.
- Headless failure modes are self-explaining.
- render_demo produces shareable mp3s with a single command.
