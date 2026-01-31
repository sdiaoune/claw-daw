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

echo "[claw-daw] Installing claw-daw from GitHub via pipx…"
# --force makes reruns idempotent across failures/partial installs.
pipx install --force "git+${REPO_URL}" || pipx upgrade "git+${REPO_URL}" || true

# Verify binary is reachable.
if ! command -v claw-daw >/dev/null 2>&1; then
  echo "[claw-daw] NOTE: 'claw-daw' is not on PATH yet." >&2
  echo "Run: pipx ensurepath  (then restart your terminal)" >&2
  echo "Or try: export PATH=\"$HOME/.local/bin:\$PATH\"" >&2
  exit 2
fi

echo
echo "[claw-daw] Done. If 'claw-daw' is not found, restart your terminal (PATH update)."
echo "Try:"
echo "  claw-daw --help"
