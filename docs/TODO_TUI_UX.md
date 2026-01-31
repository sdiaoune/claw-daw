# TUI UX improvements (next)

We added headless automation, patterns/clips, and mixer controls.
The TUI still needs a "launch-quality" UX pass.

Immediate improvements:
- Split right panel into:
  - Patterns list (name, length, #notes)
  - Clips list (pattern, start, repeats)
  - Legacy notes list
- Add view toggle keys:
  - `1` track view
  - `2` patterns/clips view
  - `3` help
- Add quick commands mapping:
  - `a` add_track prompt
  - `p` new_pattern prompt
  - `Enter` place pattern at cursor (optional)

This is mostly presentation + keybinding work; the underlying commands already exist.
