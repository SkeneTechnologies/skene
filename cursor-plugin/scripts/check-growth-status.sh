#!/usr/bin/env bash
set -euo pipefail

# Lightweight hook: silently run status check if an active growth loop exists.
# Runs after file edits. Fails silently to avoid disrupting the user.
if [ -f ".skene/active-loop.json" ] || [ -d "skene/growth-loops" ] || [ -d "skene-context/growth-loops" ]; then
  if command -v uvx &>/dev/null; then
    uvx skene status . 2>/dev/null || true
  fi
fi
