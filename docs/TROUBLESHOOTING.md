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

### Drums/samples disappear in full export
If a drum track uses `set_sample_pack` (or a native instrument) and renders fine alone
but goes missing in the full mix:
- Update to the latest build (older versions could drop track metadata when slicing
  the render region for exports).
- Clear the render region (`set_render_region none`) and re-export.

## Audio quality

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
