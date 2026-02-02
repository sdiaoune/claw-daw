# Architecture Note — Stylepacks + Scored Iteration Pipeline

This note documents the **additive** pipeline used for the Stage A→F “stylepacks + demos” work.

## Goal
Enable an agent (or CI) to generate genre-correct beats deterministically, **score** the audio quickly (simple spectral balance heuristic), and iterate a few times automatically, saving a machine-readable report.

## Pipeline (high level)

### 1) Prompt → BeatSpec
- Input can be:
  - a user prompt (free text), or
  - a **Stylepack demo YAML** (`demos/<style>/<name>.yaml`).
- The output is a **BeatSpec**: a structured, reproducible description of what to generate.

BeatSpec includes:
- `stylepack` (e.g. `trap_2020s`, `boom_bap`, `house`)
- tempo/feel parameters (bpm/swing)
- length target (bars or seconds)
- 3–6 tweak knobs (density, kit, humanize, etc.)
- seed + attempt budget

### 2) BeatSpec → validate
We validate:
- stylepack exists
- knob ranges are sane (0..1, bpm ranges)
- output names/paths are safe

### 3) BeatSpec → compile (headless script)
We compile BeatSpec into a deterministic **headless script** in `tools/<name>.txt`.
- Under the hood this uses:
  - **Genre Packs v1** (trap/house/boom_bap) for “from-scratch” generation
  - **Drum Kits v1** for role-based drums
- The compiler also injects:
  - project name
  - render/export commands

### 4) Compile → render
We execute the headless script with a SoundFont (`--soundfont`) to produce:
- `out/<name>.mp3`
- `out/<name>.mid`
- `out/<name>.json`
- (optional) `out/<name>.preview.mp3`

### 5) Render → score (spectral balance heuristic)
We analyze audio via ffmpeg volumedetect band splits.
Score is a simple 0..1 value where **1.0 = balanced** and lower scores indicate:
- too much sub/low end vs the rest
- too much high end (harsh)
- overall too quiet / too hot

This is intentionally lightweight and deterministic.

### 6) Score → iterate (up to N attempts)
If `score < threshold`, we adjust a small set of knobs and regenerate.
Example adjustments:
- increase humanize timing/velocity
- increase velocity variance
- simplify melody (reduce lead density)
- change drum kit

### 7) Deliver + report
We write `out/<name>.report.json` containing:
- BeatSpec
- attempt-by-attempt parameters
- acceptance test results
- similarity values (novelty control)
- spectral balance report + score
- chosen “best” attempt

## Non-goals (for this stage)
- Full mix/mastering engine
- Deep ML-based reference matching
- Sample-pack management

## Additive / compatibility guarantee
- Existing headless scripts keep working.
- New functionality is exposed as new commands/modules.
- Schema migrations remain backwards compatible.
