#!/usr/bin/env bash
set -euo pipefail

# claw-daw one-go installer (macOS)
# Installs Homebrew deps + installs claw-daw from GitHub via pipx.

REPO_URL="https://github.com/sdiaoune/claw-daw.git"
SOUNDFONT_URL="https://github.com/pianobooster/fluid-soundfont/releases/latest/download/FluidR3_GM.sf2"
# Best practice: pin to a tag for stable installs, e.g.
# REPO_REF="v0.1.0"
# REPO_URL="${REPO_URL}@${REPO_REF}"

if ! command -v brew >/dev/null 2>&1; then
  echo "ERROR: Homebrew not found." >&2
  echo "Install it first: https://brew.sh" >&2
  exit 1
fi

echo "[claw-daw] Installing system dependencies (fluidsynth, ffmpeg, python, pipx)…"
brew update >/dev/null 2>&1 || true
brew install fluidsynth ffmpeg python pipx
hash -r 2>/dev/null || true

if ! command -v pipx >/dev/null 2>&1; then
  echo "ERROR: pipx not found after install. Install pipx and retry." >&2
  exit 1
fi

# Ensure pipx logs are writable (avoids PermissionError on some systems)
PIPX_LOG_DIR="${PIPX_LOG_DIR:-$HOME/.local/pipx/logs}"
mkdir -p "$PIPX_LOG_DIR" >/dev/null 2>&1 || true
if [[ ! -w "$PIPX_LOG_DIR" ]]; then
  PIPX_LOG_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/pipx/logs"
  mkdir -p "$PIPX_LOG_DIR" >/dev/null 2>&1 || true
fi
export PIPX_LOG_DIR

# Some macOS setups end up with ~/.local/bin owned by root (or otherwise unwritable),
# which breaks pipx symlinking. We try to self-heal.
mkdir -p "$HOME/.local/bin" "$HOME/.local"
if [[ ! -w "$HOME/.local/bin" ]]; then
  echo "[claw-daw] '$HOME/.local/bin' is not writable. Attempting to fix permissions…" >&2
  # Best-effort: use sudo if available; if not, we'll fall back to a different bin dir.
  if command -v sudo >/dev/null 2>&1; then
    sudo chown -R "$USER" "$HOME/.local" || true
  fi
fi

# If still not writable, fall back to a user-owned bin dir.
if [[ ! -w "$HOME/.local/bin" ]]; then
  echo "[claw-daw] Still cannot write to '$HOME/.local/bin'. Falling back to '$HOME/bin'." >&2
  mkdir -p "$HOME/bin"
  export PIPX_BIN_DIR="$HOME/bin"
  export PATH="$HOME/bin:$PATH"
else
  export PIPX_BIN_DIR="$HOME/.local/bin"
  export PATH="$HOME/.local/bin:$PATH"
fi

# Ensure pipx is on PATH for future shells, and best-effort for *this* shell.
pipx ensurepath >/dev/null 2>&1 || true

echo "[claw-daw] Installing claw-daw via pipx…"
# --force makes reruns idempotent across failures/partial installs.
if ! pipx install --force "claw-daw"; then
  echo "[claw-daw] PyPI install failed; falling back to GitHub…" >&2
  pipx install --force "git+${REPO_URL}"
fi

# Ensure pipx registered the install; retry once if not.
if ! pipx list | grep -q "package claw-daw"; then
  echo "[claw-daw] pipx install did not register; retrying…" >&2
  if ! pipx install --force "claw-daw"; then
    echo "[claw-daw] PyPI install failed; falling back to GitHub…" >&2
    pipx install --force "git+${REPO_URL}"
  fi
fi

if ! pipx list | grep -q "package claw-daw"; then
  echo "[claw-daw] ERROR: pipx did not install claw-daw." >&2
  echo "Try: pipx install claw-daw" >&2
  exit 2
fi

# Verify binary is reachable.
if ! command -v claw-daw >/dev/null 2>&1; then
  echo "[claw-daw] ERROR: install completed but 'claw-daw' is not on PATH." >&2
  echo "Try: pipx list" >&2
  echo "Then run: pipx ensurepath  (and restart your terminal)" >&2
  echo "Current PATH: $PATH" >&2
  exit 2
fi

# Optional: download a GM SoundFont if none found
if [[ -z "${SKIP_SOUNDFONT:-}" ]]; then
  SF2_FOUND=""
  for p in \
    "$HOME/Library/Audio/Sounds/Banks/default.sf2" \
    "/Library/Audio/Sounds/Banks/default.sf2"; do
    if [[ -f "$p" ]]; then
      SF2_FOUND="$p"
      break
    fi
  done

  DATA_HOME="$HOME/Library/Application Support"
  SF2_DIR="$DATA_HOME/claw-daw/soundfonts"
  SF2_PATH="$SF2_DIR/FluidR3_GM.sf2"

  if [[ -z "$SF2_FOUND" && ! -f "$SF2_PATH" ]]; then
    echo "[claw-daw] No GM SoundFont found; downloading FluidR3_GM…" >&2
    mkdir -p "$SF2_DIR"
    if command -v curl >/dev/null 2>&1; then
      curl -fsSL "$SOUNDFONT_URL" -o "$SF2_PATH"
    else
      echo "[claw-daw] WARNING: curl not found; install a GM .sf2 manually." >&2
    fi
  fi
fi

echo
echo "[claw-daw] Done. If 'claw-daw' is not found, restart your terminal (PATH update)."
echo "Try:"
echo "  claw-daw --help"
