# Changelog

## Unreleased

### Fixed
- Preserve note attributes (including **role-based drum events**) when slicing projects for export, preventing cases where drums appear in stems but disappear in the rendered master.

## 0.2.1

- Synced the published skill artifacts (`docs/skill.md`, `docs/skill.json`) with the newer claw-daw agent workflow guidance.
- Added the quality-workflow and gated-render guidance missing from the published skill doc.
- Documented the new auto-seed behavior for `prompt`, `pack`, and `stylepack` while preserving explicit deterministic seeds.
- Included the skill artifacts in wheel and sdist builds so a PyPI release can ship the latest skill metadata.

## 0.2.0

- TUI UX polish: visible mode line, consistent keybinds, view toggle (`g`), mute/solo keys, metronome + count-in
- Safer project loading: schema migrations (v1→v3), validation, and hard limits
- Arrangement ops: rename/duplicate/delete patterns, move/delete clips, copy bars, render region controls
- Deterministic generators: `gen_drums` and `template_*` shortcuts
- Shareable exports: default `out/<project>.(mp3|m4a|wav)` when no path is given; `render_demo` writes a cover text file
- Mastering presets (`demo|clean|loud`) and fade-in/out on audio exports
