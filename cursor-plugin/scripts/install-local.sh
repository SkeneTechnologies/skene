#!/usr/bin/env bash
set -euo pipefail

command -v python3 >/dev/null || { echo "python3 is required but not found."; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PLUGIN_NAME="skene"
PLUGIN_ID="${PLUGIN_NAME}@local"
TARGET="$HOME/.cursor/plugins/$PLUGIN_NAME"
CLAUDE_DIR="$HOME/.claude"
CLAUDE_PLUGINS="$CLAUDE_DIR/plugins/installed_plugins.json"
CLAUDE_SETTINGS="$CLAUDE_DIR/settings.json"

echo "=== Skene — Local Install ==="
echo ""
echo "Plugin:  $PLUGIN_NAME"
echo "Source:  $REPO_ROOT"
echo "Target:  $TARGET"
echo ""

# 1. Copy plugin files
echo "[1/3] Copying plugin files..."
rm -rf "$TARGET"
mkdir -p "$TARGET"
for dir in .cursor-plugin commands rules skills hooks scripts assets; do
  if [ -e "$REPO_ROOT/$dir" ]; then
    cp -R "$REPO_ROOT/$dir" "$TARGET/"
  fi
done
echo "      Done."

# 2. Register in installed_plugins.json (upsert without clobbering other plugins)
echo "[2/3] Registering plugin..."
mkdir -p "$CLAUDE_DIR/plugins"
python3 - "$CLAUDE_PLUGINS" "$PLUGIN_ID" "$TARGET" <<'PY'
import json, os, sys
path, pid, ipath = sys.argv[1], sys.argv[2], sys.argv[3]
data = {}
if os.path.exists(path):
    try:
        data = json.load(open(path))
    except Exception:
        data = {}
plugins = data.get("plugins", {})
entries = [e for e in plugins.get(pid, [])
           if not (isinstance(e, dict) and e.get("scope") == "user")]
entries.insert(0, {"scope": "user", "installPath": ipath})
plugins[pid] = entries
data["plugins"] = plugins
os.makedirs(os.path.dirname(path), exist_ok=True)
json.dump(data, open(path, "w"), indent=2)
PY
echo "      Done."

# 3. Enable in settings.json (upsert without clobbering other settings)
echo "[3/3] Enabling plugin..."
python3 - "$CLAUDE_SETTINGS" "$PLUGIN_ID" <<'PY'
import json, os, sys
path, pid = sys.argv[1], sys.argv[2]
data = {}
if os.path.exists(path):
    try:
        data = json.load(open(path))
    except Exception:
        data = {}
data.setdefault("enabledPlugins", {})[pid] = True
os.makedirs(os.path.dirname(path), exist_ok=True)
json.dump(data, open(path, "w"), indent=2)
PY
echo "      Done."

echo ""
echo "=== Install complete ==="
echo ""
echo "Next steps:"
echo "  1. Restart Cursor (Cmd+Shift+P → 'Reload Window', or quit and reopen)"
echo "  2. Open the command palette and try /skene-init"
echo ""
echo "To uninstall, run: bash $SCRIPT_DIR/uninstall-local.sh"
