# Pre-launch plan: 3 must-have features

This plan covers the **3 features** requested before launch:

1) **Arrangement / Patterns**
2) **Proper mixer + dynamics**
3) **Agent/human automation contract**

Constraints: offline-only, terminal-only, local files only.

---

## 1) Arrangement / Patterns

### Goal
Support building a 1-minute song by composing **patterns** (reusable clips) and placing them on a **timeline**.

### Data model additions
- `Pattern`: name, length_ticks, notes (relative ticks)
- `Clip`: pattern_name, start_tick, repeats
- `Track` adds:
  - `patterns: dict[str, Pattern]`
  - `clips: list[Clip]`

### Commands (TUI and headless)
- `new_pattern <track> <pattern_name> <length_ticks>`
- `add_note_pat <track> <pattern> <pitch> <start> <dur> [vel]`
- `del_note_pat <track> <pattern> <note_index>`
- `place_pattern <track> <pattern> <start_tick> [repeats]`
- `clear_clips <track>`

### Export behavior
- If a track has clips, render from clips; otherwise fall back to legacy `track.notes`.

Exit criteria:
- Create two patterns and place them across 24 bars; MIDI/WAV export reflects arrangement.

---

## 2) Proper mixer + dynamics

### Goal
Make exports sound more “finished” and provide basic mix control.

### Track controls
- Already: volume (CC7), pan (CC10)
- Add:
  - reverb send (CC91)
  - chorus send (CC93)

### Master processing
- Post-render normalization + resample + optional trim:
  - Apply ffmpeg `loudnorm` + set `-ar 44100` and optional `-t 60` so exports are consistent and small.
Exit criteria:
- Exported WAV sounds consistent in level; tracks can be widened via pan and have optional reverb.

---

## 3) Agent/human automation contract

### Goal
Make the DAW controllable without curses for repeatable automation.

### Headless mode
Add a CLI mode that:
- Reads commands from a script file or stdin
- Executes them using the same command parser as the TUI
- Can export midi/wav, dump state

### State dump
- `--dump-state <path>` writes full project state JSON (including patterns/clips) deterministically.

Exit criteria:
- One-line command runs a script and renders a song to wav/mp3 without TUI.

---

## Suggested implementation order
1) Update model + JSON persistence for patterns/clips
2) Update MIDI exporter to render clips (and mixer CCs)
3) Add headless command runner + state dump
4) Update TUI commands to manage patterns/clips + mixer params
5) Add master loudness normalization on WAV export
6) Compose and render 1-minute track (24 bars @ 96 BPM)
