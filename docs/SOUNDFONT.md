# SoundFont (SF2)

claw-daw uses **FluidSynth** with a **SoundFont (.sf2)** for offline synthesis.

## Getting a GM SoundFont

Common General MIDI SoundFonts:
- FluidR3_GM.sf2 (often packaged with distributions)

On Debian/Ubuntu you may find packages like `fluid-soundfont-gm` / `fluid-soundfont-gs`.

## Config

On first run, claw-daw will prompt for a SoundFont path and store it in:

`~/.config/claw-daw/config.json`

You can edit that file manually if needed.
