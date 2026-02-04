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

- Render bus stems (heuristic grouping by track name: drums/bass/music):
```txt
export_busses out/busses
```

- Meter an audio file (writes JSON with LUFS/true-peak/crest/DC offset/correlation):
```txt
meter_audio out/my_song.mp3 out/my_song.meter.json
```

- Use a mix spec (track EQ/comp/gate/saturation/stereo tools, sends/returns, sidechain) during export:
```txt
export_wav out/my_song.wav preset=demo mix=tools/mix.json
export_mp3 out/my_song.mp3 preset=demo mix=tools/mix.json
```
