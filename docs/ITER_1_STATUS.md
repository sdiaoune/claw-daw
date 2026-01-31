# Iteration 1 status

## Implemented

### Headless automation contract
- `--headless` runner now supports `include <file>` (relative to script dir)
- CLI flags:
  - `--strict` (stop on first error)
  - `--dry-run` (skip renders/exports)
- `dump_state <path>` now includes deterministic derived fields:
  - `derived.song_length_ticks`
  - `derived.song_length_seconds`
  - `derived.song_bars_estimate`

### Schema hardening
- `Project.to_dict()` now writes `schema_version: 2`
- Project load runs `validate_and_migrate_project()` to clamp/sanitize values

### Export reliability
- FluidSynth WAV render uses `-r 44100` by default
- Headless export supports `trim=` and `sr=` options on export_wav
- Added `export_mp3` and `export_m4a` headless commands

### Agent cookbook + templates
- `docs/AGENT_COOKBOOK.md`
- `templates/hiphop_1min.txt`, `templates/lofi_1min.txt`, `templates/house_1min.txt`
- Verified all templates produce mp3 outputs

## Tests
- Added `tests/test_headless_contract.py` (include + dump_state)
- `pytest` passing

## Remaining in this iteration
- TUI UX polish is not fully implemented yet (headless path is solid). Next iteration should target TUI views + keybind stability.
