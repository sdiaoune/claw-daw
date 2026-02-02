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
# then download a GM .sf2
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

## Generate a stylepack beat directly
```bash
claw-daw stylepack trap_2020s --out my_trap --soundfont /usr/share/sounds/sf2/default-GM.sf2 \
  --seed 2026 --attempts 6 --bars 36 --score-threshold 0.62 \
  --knob drum_density=0.84 --knob lead_density=0.55
```
