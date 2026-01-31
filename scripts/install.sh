#!/usr/bin/env bash
set -euo pipefail

# claw-daw installer (Debian/Ubuntu)
# Installs system deps + pipx package.

if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  SUDO=""
else
  if command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
  else
    echo "ERROR: sudo not found and you are not root." >&2
    exit 1
  fi
fi

if ! command -v apt-get >/dev/null 2>&1; then
  echo "ERROR: apt-get not found. This script is for Debian/Ubuntu." >&2
  echo "macOS: brew install fluidsynth ffmpeg && pipx install claw-daw" >&2
  exit 1
fi

echo "[claw-daw] Installing system dependencies (fluidsynth, ffmpeg, soundfont, pipx)…"
$SUDO apt-get update -y
$SUDO apt-get install -y \
  fluidsynth \
  ffmpeg \
  fluid-soundfont-gm \
  python3 \
  python3-venv \
  python3-pip \
  pipx

# Make sure pipx bin path is available in this shell.
# (Some environments require a new shell; we keep it best-effort.)
python3 -m pipx ensurepath >/dev/null 2>&1 || true

if ! command -v pipx >/dev/null 2>&1; then
  echo "ERROR: pipx did not install correctly." >&2
  exit 1
fi

echo "[claw-daw] Installing claw-daw via pipx…"
pipx install claw-daw || pipx upgrade claw-daw

echo
echo "[claw-daw] Done. Try:"
echo "  claw-daw"
echo
echo "SoundFont check:"
echo "  ls -lah /usr/share/sounds/sf2/default-GM.sf2"
