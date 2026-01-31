#!/usr/bin/env bash
set -euo pipefail

# claw-daw one-go installer (macOS)
# Installs Homebrew deps + installs claw-daw from GitHub via pipx.

REPO_URL="https://github.com/sdiaoune/claw-daw.git"
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

# Ensure pipx is on PATH for future shells, and best-effort for *this* shell.
pipx ensurepath >/dev/null 2>&1 || true
export PATH="$HOME/.local/bin:$PATH"

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
fi

echo "[claw-daw] Installing claw-daw from GitHub via pipx…"
# --force makes reruns idempotent across failures/partial installs.
pipx install --force "git+${REPO_URL}"

# Verify binary is reachable.
if ! command -v claw-daw >/dev/null 2>&1; then
  echo "[claw-daw] ERROR: install completed but 'claw-daw' is not on PATH." >&2
  echo "Try: pipx list" >&2
  echo "Then run: pipx ensurepath  (and restart your terminal)" >&2
  echo "Current PATH: $PATH" >&2
  exit 2
fi

echo
echo "[claw-daw] Done. If 'claw-daw' is not found, restart your terminal (PATH update)."
echo "Try:"
echo "  claw-daw --help"
