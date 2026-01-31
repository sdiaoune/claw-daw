#!/usr/bin/env bash
set -euo pipefail

# claw-daw one-go installer (Linux)
#
# Goal: install system deps (fluidsynth + ffmpeg + a GM soundfont when available)
# then install claw-daw from GitHub via pipx.

REPO_URL="https://github.com/sdiaoune/claw-daw.git"

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

pm=""
if command -v apt-get >/dev/null 2>&1; then pm="apt"; fi
if command -v dnf >/dev/null 2>&1; then pm="dnf"; fi
if command -v yum >/dev/null 2>&1 && [[ -z "$pm" ]]; then pm="yum"; fi
if command -v pacman >/dev/null 2>&1; then pm="pacman"; fi

if [[ -z "$pm" ]]; then
  echo "ERROR: Unsupported Linux (no apt-get/dnf/yum/pacman found)." >&2
  echo "Install manually: fluidsynth + ffmpeg + a GM soundfont + pipx, then:" >&2
  echo "  pipx install 'git+${REPO_URL}'" >&2
  exit 1
fi

echo "[claw-daw] Detected package manager: $pm"

echo "[claw-daw] Installing system dependencies (fluidsynth, ffmpeg, soundfont, python, pipx)…"
case "$pm" in
  apt)
    $SUDO apt-get update -y
    $SUDO apt-get install -y \
      fluidsynth ffmpeg fluid-soundfont-gm \
      python3 python3-venv python3-pip pipx
    ;;
  dnf)
    $SUDO dnf -y install \
      fluidsynth ffmpeg fluid-soundfont-gm \
      python3 python3-pip pipx || true
    ;;
  yum)
    $SUDO yum -y install \
      fluidsynth ffmpeg fluid-soundfont-gm \
      python3 python3-pip pipx || true
    ;;
  pacman)
    $SUDO pacman -Sy --noconfirm \
      fluidsynth ffmpeg soundfont-fluid \
      python python-pip python-pipx || true
    ;;
esac

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found after install. Install Python 3 and retry." >&2
  exit 1
fi

if ! command -v pipx >/dev/null 2>&1; then
  echo "[claw-daw] pipx not found via system packages; installing with pip --user…" >&2
  python3 -m pip install --user --upgrade pip pipx
fi

python3 -m pipx ensurepath >/dev/null 2>&1 || true
export PATH="$HOME/.local/bin:$PATH"

echo "[claw-daw] Installing claw-daw from GitHub via pipx…"
pipx install --force "git+${REPO_URL}"

echo
echo "[claw-daw] Done. Try:"
echo "  claw-daw --help"
