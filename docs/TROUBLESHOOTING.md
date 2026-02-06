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

### Error: Unknown command `scan_sample_pack`
Cause:
- You are running an older CLI (e.g., a pipx install) that predates sample-pack commands.

Fix:
- Use the repo CLI: `python3 -m claw_daw --headless --script tools/<name>.txt`
- Or set `CLAW_DAW_CLI="python3 -m claw_daw"` so tools like `preview_gate.py` use the local CLI.

### preview_gate passes, master gate fails (true-peak)
Cause:
- Preview was generated with a different CLI or a short segment that misses true-peak spikes.
- MP3 encoding can create inter-sample peaks higher than the limiter ceiling.

Fix / Prevention:
- Ensure preview and export use the same CLI (`CLAW_DAW_CLI=...`).
- Use the latest `clean` mastering preset (lower limiter headroom).
- Preview and export now meter the **master WAV** by default to avoid MP3 overs.
- If it still fails, increase headroom slightly in the mix spec (reduce `gain_db`).

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

### I lowered a track in the mix, but the exported stems are still loud

Symptom:
- You set a mix spec track `gain_db` (e.g. to lower the lead), the **master MP3** changes, but **exported stems** stay at the old level.

Cause:
- Historically, `export_stems` rendered stems *pre-mix* (dry per-track renders) and did not apply the mix spec.

Fix / Prevention:
- Use `export_package ... stems=1 mix=tools/mix.json` (or `export_stems <dir> mix=tools/mix.json`) so stems inherit **track-level** mix processing.
- If you want stems to be totally dry (no mix), export stems without the `mix=` argument.


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
