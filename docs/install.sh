#!/usr/bin/env bash
set -euo pipefail

# claw-daw one-go installer (Linux)
#
# Goal: install system deps (fluidsynth + ffmpeg + a GM soundfont when available)
# then install claw-daw from GitHub via pipx.
#
# Notes:
# - "One-go" on Linux is best on Debian/Ubuntu. Other distros vary (ffmpeg repos, soundfont packages).
# - This script is best-effort across common distros (apt, dnf, yum, pacman).

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

# Best-effort installs across distros.
case "$pm" in
  apt)
    $SUDO apt-get update -y
    # fluid-soundfont-gm provides /usr/share/sounds/sf2/default-GM.sf2 on many distros
    $SUDO apt-get install -y \
      fluidsynth ffmpeg fluid-soundfont-gm \
      python3 python3-venv python3-pip pipx
    ;;
  dnf)
    $SUDO dnf -y install \
      fluidsynth ffmpeg \
      fluid-soundfont-gm \
      python3 python3-pip pipx || true
    ;;
  yum)
    $SUDO yum -y install \
      fluidsynth ffmpeg \
      fluid-soundfont-gm \
      python3 python3-pip pipx || true
    ;;
  pacman)
    $SUDO pacman -Sy --noconfirm \
      fluidsynth ffmpeg \
      soundfont-fluid \
      python python-pip python-pipx || true
    ;;
esac

# Ensure python3 exists
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found after install. Install Python 3 and retry." >&2
  exit 1
fi

# Ensure pipx exists (fallback to user install)
if ! command -v pipx >/dev/null 2>&1; then
  echo "[claw-daw] pipx not found via system packages; installing with pip --user…" >&2
  python3 -m pip install --user --upgrade pip pipx
fi

# Make sure pipx bin path is available in this shell.
python3 -m pipx ensurepath >/dev/null 2>&1 || true
export PATH="$HOME/.local/bin:$PATH"

if ! command -v pipx >/dev/null 2>&1; then
  echo "ERROR: pipx did not install correctly." >&2
  exit 1
fi

echo "[claw-daw] Installing claw-daw from GitHub via pipx…"
# Use --force for idempotency; avoid `pipx upgrade` with a URL.
pipx install --force "git+${REPO_URL}"

# Verify binary
if ! command -v claw-daw >/dev/null 2>&1; then
  echo "[claw-daw] ERROR: install completed but 'claw-daw' is not on PATH." >&2
  echo "Try: export PATH=\"$HOME/.local/bin:\$PATH\"" >&2
  echo "Then: claw-daw --help" >&2
  exit 2
fi

echo
echo "[claw-daw] Done. Try:"
echo "  claw-daw --help"
echo
echo "SoundFont tip: if exports fail, install a GM .sf2 and/or pass --soundfont /path/to.sf2"
