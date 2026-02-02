# claw-daw

Offline, terminal-only MIDI DAW MVP.

## Quickstart (Phase 0)

```bash
python3 -m pip install -e .
python3 -m claw_daw
# or
claw-daw
```

## Notes
- 100% offline core (no network APIs).
- Projects are stored as human-readable JSON (schema v5) and exported to .mid/.wav/.mp3/.m4a.
- Rendering pipeline:
  - SoundFont tracks via FluidSynth
  - Built-in sampler tracks: `drums` + `808` (with glide)
  - Deterministic mastering presets via ffmpeg (`demo|clean|lofi`)
- Agent-friendly ergonomics:
  - bar:beat syntax for time args (e.g. `2:0`)
  - pattern transform primitives
  - reference analysis + diff/validation commands
