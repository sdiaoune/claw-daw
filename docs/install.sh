#!/usr/bin/env bash
set -euo pipefail

# claw-daw one-go installer (Debian/Ubuntu)
# Installs system deps + installs claw-daw from GitHub via pipx.

REPO_URL="https://github.com/sdiaoune/claw-daw.git"
# Best practice: pin to a tag for stable installs, e.g.
# REPO_REF="v0.1.0"
# REPO_URL="${REPO_URL}@${REPO_REF}"

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
  echo "macOS: brew install fluidsynth ffmpeg && pipx install 'git+${REPO_URL}'" >&2
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
python3 -m pipx ensurepath >/dev/null 2>&1 || true

if ! command -v pipx >/dev/null 2>&1; then
  echo "ERROR: pipx did not install correctly." >&2
  exit 1
fi

echo "[claw-daw] Installing claw-daw from GitHub via pipx…"
pipx install "git+${REPO_URL}" || pipx upgrade "git+${REPO_URL}"

echo
echo "[claw-daw] Done. Try:"
echo "  claw-daw"
echo
echo "SoundFont check:"
echo "  ls -lah /usr/share/sounds/sf2/default-GM.sf2"
