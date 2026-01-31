# Spectrogram Feature (claw-daw)

We added a simple, dependency-free spectrogram feature using **ffmpeg**.

## Why
- Visualize low-end vs mids/highs to catch **bass masking** quickly.
- Generate a consistent PNG for every iteration.
- Create reference spectrograms for external tracks and A/B against your beat.

## Commands (headless)

### 1) Export spectrogram from current project
Requires a loaded project + soundfont.

```txt
open_project out/my_beat.json
export_spectrogram out/my_beat.spectrogram.png
```

Optional args:
- `sr=44100`
- `size=1200x600`
- `legend=1` (or `0`)
- `color=fiery`
- `scale=log`
- `gain=5`

This generates:
- `out/my_beat.spectrogram.png`
- `out/my_beat.spectrogram.bands.txt` (quick band-energy summary)

### 2) Spectrogram for an arbitrary audio file (reference)
Does **not** require a project.

```txt
spectrogram_audio refs/track.mp3 out/track_ref.spectrogram.png
```

Also writes:
- `out/track_ref.spectrogram.bands.txt`

## Band report (what it means)
The `.bands.txt` file is a fast heuristic to estimate how much energy is in the sub vs the rest:
- `sub<90` uses `lowpass=f=90`
- `rest>=90` uses `highpass=f=90`

If `sub<90.mean_db` is much higher (less negative) than `rest>=90.mean_db`, the low end may be dominating.

## Implementation
- `claw_daw/audio/spectrogram.py`
- `export_spectrogram` + `spectrogram_audio` commands in `claw_daw/cli/headless.py`

## Notes
- This uses ffmpeg filters `showspectrumpic` + `volumedetect`.
- Spectrograms are best used as a **visual cross-check**, not a replacement for ears.
