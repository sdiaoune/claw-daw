# Troubleshooting — claw-daw

## SoundFont problems

### Error: missing soundfont / default-GM.sf2
If `/usr/share/sounds/sf2/default-GM.sf2` does not exist, provide a SoundFont explicitly:

```bash
claw-daw --soundfont /path/to/YourGM.sf2
```

On Ubuntu/Debian you can install one:

```bash
sudo apt-get install fluid-soundfont-gm
```

## Binary dependencies

### fluidsynth not found
Install:

```bash
sudo apt-get install fluidsynth
```

### ffmpeg not found
Install:

```bash
sudo apt-get install ffmpeg
```

## Headless script issues

### My script runs but hangs
Some exports may take a while depending on track count and render length.
Try:
- reduce length (use `set_render_region`)
- export WAV only first (then encode MP3 separately)

If you suspect a hang, inspect temporary files:
- `out/<project>.tmp.track*.wav` are per-track renders used for stems/mixing.

## Audio quality

### Drums audible in stems but missing in exported MP3/WAV

Symptom:
- `export_stems` shows a `00_Drums.wav` with audio, but the main `export_mp3` / `export_wav` sounds like it has no drums.

Cause:
- This can happen if the project uses **role-based drum notes** (kick/snare/hh/oh) and an intermediate step that slices/flattens the arrangement drops note attributes like `role`.
- Without `role`, drum events can’t be expanded/converted correctly for GM drum rendering.

Fix:
- Ensure the render/slice pipeline preserves note attributes (at minimum: `role`, `chance`, `mute`, `accent`, `glide_ticks`).
- claw-daw now preserves these attributes when slicing projects for export.

### “Instruments sound fake”
claw-daw uses GM SoundFonts and a simple synth pipeline.
Improving realism typically means:
- use a higher-quality SoundFont (`.sf2`)
- reduce “GM” exposure (less bright presets, more reverb/delay)
- use sampler one-shots for drums/808

If you need modern producer-quality instruments, you’ll want a sampler/VST workflow outside of claw-daw.

## Sampler limitations

Sampler mode is currently limited to:
- `set_sampler <track> drums`
- `set_sampler <track> 808`

Loading a `.zip` sample pack directly from the TUI is **not implemented** yet.
