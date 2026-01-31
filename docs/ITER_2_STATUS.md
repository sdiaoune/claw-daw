# Iteration 2 status

## Implemented

### 1) TUI stable views + keybind stability
- Added `view` concept to TUI (`tracks` vs `arrange`)
- Keybinds:
  - `1` → Tracks/Mixer view
  - `2` → Arrange view
  - `:` command mode
  - `?` help
  - Up/Down select track
  - Space play/stop
- Arrange view shows patterns and clips for selected track.

### 2) Headless error reporting / diagnostics
- `include` supports relative paths (resolved from script dir)
- Missing include:
  - strict: raises FileNotFoundError
  - non-strict: warning and continue
- Strict mode errors now include line number + command text.
- Added counters: `commands_executed` and warnings list (internal).

### 3) One-command demo render
- Added headless command:
  - `render_demo <style> <out_prefix>`
  - styles: hiphop | lofi | house
  - produces `<out_prefix>.mp3`, `.mid`, `.json`
- Verified via strict headless run.

## Tests
- Existing tests pass.
- Manual: `render_demo` generated 3 mp3s.

## Notes
- TUI remains intentionally "command-driven" for deterministic agent control.
- Next iterations should focus on packaging, docs polish, and more arrangement ops (duplicate/rename/move clip).
