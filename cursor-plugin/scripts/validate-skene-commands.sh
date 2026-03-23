#!/usr/bin/env bash
set -euo pipefail

if ! command -v uvx &>/dev/null; then
  echo "Warning: uvx is not installed. Install it with: pip install uv"
  exit 1
fi

if [ ! -f ".skene.config" ]; then
  echo "Warning: Skene is not configured. Run /skene-init first."
fi
