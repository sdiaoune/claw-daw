from __future__ import annotations

"""Hard limits to prevent footguns / runaway projects.

These limits are intentionally conservative for an MVP TUI/agent workflow.
They are enforced in commands (headless + TUI) and on project load.
"""

MAX_TRACKS = 16  # MIDI channel limit anyway
MAX_PATTERNS_PER_TRACK = 128
MAX_CLIPS_PER_TRACK = 2048
MAX_NOTES_PER_TRACK = 50000
MAX_NOTES_PER_PATTERN = 8192

# Keep tick values sane (avoid pathological ints in JSON)
MAX_TICK = 10_000_000
