#!/usr/bin/env bash
set -euo pipefail

command -v python3 >/dev/null || { echo "python3 is required but not found."; exit 1; }

PLUGIN_NAME="skene"
PLUGIN_ID="${PLUGIN_NAME}@local"
TARGET="$HOME/.cursor/plugins/$PLUGIN_NAME"
CLAUDE_PLUGINS="$HOME/.claude/plugins/installed_plugins.json"
CLAUDE_SETTINGS="$HOME/.claude/settings.json"

echo "=== Skene — Uninstall ==="

# 1. Remove plugin files
echo "[1/3] Removing plugin files..."
rm -rf "$TARGET"
echo "      Done."

# 2. Remove from installed_plugins.json
echo "[2/3] Deregistering plugin..."
if [ -f "$CLAUDE_PLUGINS" ]; then
  python3 - "$CLAUDE_PLUGINS" "$PLUGIN_ID" <<'PY'
import json, os, sys
path, pid = sys.argv[1], sys.argv[2]
if not os.path.exists(path):
    sys.exit(0)
try:
    data = json.load(open(path))
except Exception:
    sys.exit(0)
plugins = data.get("plugins", {})
plugins.pop(pid, None)
data["plugins"] = plugins
json.dump(data, open(path, "w"), indent=2)
PY
fi
echo "      Done."

# 3. Remove from settings.json
echo "[3/3] Disabling plugin..."
if [ -f "$CLAUDE_SETTINGS" ]; then
  python3 - "$CLAUDE_SETTINGS" "$PLUGIN_ID" <<'PY'
import json, os, sys
path, pid = sys.argv[1], sys.argv[2]
if not os.path.exists(path):
    sys.exit(0)
try:
    data = json.load(open(path))
except Exception:
    sys.exit(0)
data.get("enabledPlugins", {}).pop(pid, None)
json.dump(data, open(path, "w"), indent=2)
PY
fi
echo "      Done."

echo ""
echo "=== Uninstall complete. Restart Cursor. ==="
