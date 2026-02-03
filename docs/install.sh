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
SOUNDFONT_URL="https://github.com/pianobooster/fluid-soundfont/releases/latest/download/FluidR3_GM.sf2"
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
  echo "  pipx install claw-daw" >&2
  echo "  # (fallback) pipx install 'git+${REPO_URL}'" >&2
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

# Ensure pipx logs are writable (avoids PermissionError on some systems)
PIPX_LOG_DIR="${PIPX_LOG_DIR:-$HOME/.local/pipx/logs}"
mkdir -p "$PIPX_LOG_DIR" >/dev/null 2>&1 || true
if [[ ! -w "$PIPX_LOG_DIR" ]]; then
  PIPX_LOG_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/pipx/logs"
  mkdir -p "$PIPX_LOG_DIR" >/dev/null 2>&1 || true
fi
export PIPX_LOG_DIR

# Ensure pipx bin dir is writable; fall back if needed.
mkdir -p "$HOME/.local/bin" "$HOME/.local" >/dev/null 2>&1 || true
if [[ ! -w "$HOME/.local/bin" ]]; then
  echo "[claw-daw] '$HOME/.local/bin' is not writable. Falling back to '$HOME/bin'." >&2
  mkdir -p "$HOME/bin"
  export PIPX_BIN_DIR="$HOME/bin"
  export PATH="$HOME/bin:$PATH"
else
  export PIPX_BIN_DIR="$HOME/.local/bin"
  export PATH="$HOME/.local/bin:$PATH"
fi

# Make sure pipx bin path is available in this shell.
python3 -m pipx ensurepath >/dev/null 2>&1 || true

if ! command -v pipx >/dev/null 2>&1; then
  echo "ERROR: pipx did not install correctly." >&2
  exit 1
fi

echo "[claw-daw] Installing claw-daw via pipx…"
# Use --force for idempotency; avoid `pipx upgrade` with a URL.
if ! pipx install --force "claw-daw"; then
  echo "[claw-daw] PyPI install failed; falling back to GitHub…" >&2
  pipx install --force "git+${REPO_URL}"
fi

# Verify binary
if ! command -v claw-daw >/dev/null 2>&1; then
  echo "[claw-daw] ERROR: install completed but 'claw-daw' is not on PATH." >&2
  echo "Run: pipx ensurepath  (then restart your terminal)" >&2
  echo "Or add: export PATH=\"${PIPX_BIN_DIR:-$HOME/.local/bin}:\$PATH\"" >&2
  echo "Then: claw-daw --help" >&2
  exit 2
fi

# Optional: download a GM SoundFont if none found
if [[ -z "${SKIP_SOUNDFONT:-}" ]]; then
  SF2_FOUND=""
  for p in \
    "/usr/share/sounds/sf2/default-GM.sf2" \
    "/usr/share/sounds/sf2/FluidR3_GM.sf2" \
    "/usr/share/sounds/sf2/GeneralUser-GS-v1.471.sf2" \
    "/usr/share/soundfonts/FluidR3_GM.sf2" \
    "/usr/share/soundfonts/default.sf2"; do
    if [[ -f "$p" ]]; then
      SF2_FOUND="$p"
      break
    fi
  done

  DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
  SF2_DIR="$DATA_HOME/claw-daw/soundfonts"
  SF2_PATH="$SF2_DIR/FluidR3_GM.sf2"

  if [[ -z "$SF2_FOUND" && ! -f "$SF2_PATH" ]]; then
    echo "[claw-daw] No GM SoundFont found; downloading FluidR3_GM…" >&2
    mkdir -p "$SF2_DIR"
    if command -v curl >/dev/null 2>&1; then
      curl -fsSL "$SOUNDFONT_URL" -o "$SF2_PATH"
    elif command -v wget >/dev/null 2>&1; then
      wget -O "$SF2_PATH" "$SOUNDFONT_URL"
    else
      echo "[claw-daw] WARNING: curl/wget not found; install a GM .sf2 manually." >&2
    fi
  fi
fi

echo
echo "[claw-daw] Done. Try:"
echo "  claw-daw --help"
echo
echo "SoundFont tip: if exports fail, install a GM .sf2 and/or pass --soundfont /path/to.sf2"
