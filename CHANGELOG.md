# Changelog

## 0.2.0

- TUI UX polish: visible mode line, consistent keybinds, view toggle (`g`), mute/solo keys, metronome + count-in
- Safer project loading: schema migrations (v1→v3), validation, and hard limits
- Arrangement ops: rename/duplicate/delete patterns, move/delete clips, copy bars, render region controls
- Deterministic generators: `gen_drums` and `template_*` shortcuts
- Shareable exports: default `out/<project>.(mp3|m4a|wav)` when no path is given; `render_demo` writes a cover text file
- Mastering presets (`demo|clean|loud`) and fade-in/out on audio exports

