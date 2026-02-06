# Commands (install, validate, demos, tests)

## Install deps

Python deps:
```bash
python -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -e .
```

System deps (Linux):
```bash
sudo apt-get update
sudo apt-get install -y fluidsynth ffmpeg fluid-soundfont-gm
```

macOS:
```bash
brew install fluidsynth ffmpeg
# then install a GM .sf2
```

Windows (PowerShell):
```powershell
iwr https://www.clawdaw.com/install_win.ps1 -UseBasicParsing -OutFile $env:TEMP\clawdaw-install.ps1
& $env:TEMP\clawdaw-install.ps1
```
Run in Administrator PowerShell to install system deps (Chocolatey).
If `claw-daw` is not found after install, run `pipx ensurepath` and restart your terminal.

## Verify install
```bash
claw-daw --version
claw-daw doctor
```

## Run validation / health check
```bash
claw-daw doctor
claw-daw paths --soundfont
```

## Compile demos (BeatSpec YAML → tools/*.txt)
```bash
claw-daw demos compile
```

## Render demos (tools/*.txt → out/*.mp3/.mid/.json/.report.json)
```bash
claw-daw demos render --soundfont /usr/share/sounds/sf2/default-GM.sf2
```

## Run tests
```bash
pytest -q
ruff check .
```

## Generate a stylepack beat directly (opt-in)
Use this only when you explicitly want scored iteration + `out/<name>.report.json`.
The default “full artistic freedom” workflow is to write/edit a headless script in `tools/<name>.txt`.

```bash
claw-daw stylepack trap_2020s --out my_trap --soundfont /usr/share/sounds/sf2/default-GM.sf2 \
  --seed 2026 --attempts 6 --bars 36 --score-threshold 0.62 \
  --knob drum_density=0.84 --knob lead_density=0.55
```

## Sound engineering helpers (headless scripts)

- Native instrument plugins (offline render-only):
```txt
list_instruments
set_instrument 2 pluck.karplus preset=dark_pluck tone=0.55 decay=0.30 drive=1.2 width=1.15 seed=7
```

- Sample packs (drum one-shots from a folder of WAVs):
```txt
scan_sample_pack /path/to/pack id=melodic_house
list_sample_packs
set_sample_pack 0 melodic_house seed=7 gain_db=-1.5
convert_sample_pack_to_sf2 melodic_house out/melodic_house.sf2 tool=sfz2sf2
```
Tip: set `CLAW_DAW_SF2_CONVERTER=/path/to/your/tool` to override the converter binary.

- Render bus stems (explicit track bus assignment via `set_bus`, fallback is heuristic grouping):
```txt
set_bus 0 drums
set_bus 1 bass
set_bus 2 music
export_busses out/busses
```

- Meter an audio file (writes JSON with LUFS/true-peak/crest/DC offset/correlation):
```txt
meter_audio out/my_song.mp3 out/my_song.meter.json
```

- Use a mix spec (track EQ/comp/gate/expander/saturation/stereo tools, transient, sends/returns, sidechain, bus/master mono-maker) during export:
```txt
export_wav out/my_song.wav preset=demo mix=tools/mix.json
export_mp3 out/my_song.mp3 preset=demo mix=tools/mix.json
```

- Inline mix-spec helpers (writes to project JSON’s `mix` field):
```txt
eq track=1 type=bell f=300 q=1.0 g=-3
sidechain src=0 dst=1 threshold_db=-24 ratio=6 attack_ms=5 release_ms=120
transient track=0 attack=0.25 sustain=-0.10
```

- Doctor audio QA:
```bash
claw-daw doctor --audio out/my_song.mp3  # includes LUFS (integrated+short-term), true peak, balance/tilt + mix sanity warnings
```
