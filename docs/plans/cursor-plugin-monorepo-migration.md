# Cursor Plugin — Monorepo Migration Plan

## Overview

The Cursor marketplace supports a **multi-plugin repo** format: a root-level `.cursor-plugin/marketplace.json` that lists only the plugins to expose. `src/skene/`, `tui/`, and all other monorepo content are simply not listed and are invisible to Cursor. This plan adds that manifest alongside the plugin migration, making the result both locally installable and marketplace-compliant.

Move `skene-cursor-plugin` into the `skene` monorepo as `cursor-plugin/`. No git history preservation is required — the contents will be added in a single commit. The old repo will be archived on GitHub once the migration is verified.

---

## Target structure

```
skene/
├── .cursor-plugin/
│   └── marketplace.json      ← NEW: root marketplace manifest
├── src/skene/                ← Python CLI (ignored by Cursor)
├── tui/                      ← Go TUI (ignored by Cursor)
├── skene-context/            ← (ignored by Cursor)
├── cursor-plugin/            ← NEW: plugin lives here
│   ├── .cursor-plugin/
│   │   └── plugin.json
│   ├── assets/
│   ├── commands/
│   ├── hooks/
│   ├── rules/
│   ├── scripts/
│   │   ├── install-local.sh
│   │   ├── uninstall-local.sh
│   │   ├── check-growth-status.sh
│   │   └── validate-skene-commands.sh
│   ├── skills/
│   ├── CHANGELOG.md
│   ├── LICENSE
│   └── README.md
└── ...
```

---

## Step 1 — Copy the files

From the root of the `skene` repo:

```bash
cp -R ../skene-cursor-plugin/. cursor-plugin/

# Drop the old repo's git artifacts
rm -rf cursor-plugin/.git
rm -f  cursor-plugin/.gitattributes
```

---

## Step 2 — Create root `.cursor-plugin/marketplace.json`

This is the file that makes the repo marketplace-compliant. Create it at the repo root:

```bash
mkdir -p .cursor-plugin
```

```json
{
  "name": "skene",
  "owner": {
    "name": "Skene Technologies",
    "email": "hello@skene.ai"
  },
  "plugins": [
    {
      "name": "skene",
      "source": "./cursor-plugin"
    }
  ]
}
```

Cursor follows `./cursor-plugin`, finds `cursor-plugin/.cursor-plugin/plugin.json`, and stops. Everything else in the repo is ignored.

---

## Step 3 — Update `cursor-plugin/.cursor-plugin/plugin.json`

The `repository` field points to the old standalone repo and needs updating:

```diff
-  "repository": "https://github.com/SkeneTechnologies/skene-cursor-plugin",
+  "repository": "https://github.com/SkeneTechnologies/skene",
```

---

## Step 4 — Verify `hooks/hooks.json` (likely fine, but test it)

The hooks reference scripts with relative paths:

```json
"./scripts/check-growth-status.sh"
"./scripts/validate-skene-commands.sh"
```

Cursor resolves these relative to the plugin root (`cursor-plugin/`), not the repo root. Since the internal layout of `cursor-plugin/` is unchanged, these **should keep working**. Verify by installing the plugin locally after the move and triggering a file edit to confirm the hooks fire correctly.

---

## Step 5 — Verify `scripts/install-local.sh` (no changes needed)

`install-local.sh` derives `REPO_ROOT` via `dirname` of the script itself, then copies sibling directories relative to that root. The internal layout inside `cursor-plugin/` is identical to the old repo root, so the script works without modification.

Quick sanity check — run from the repo root and confirm:

```bash
bash cursor-plugin/scripts/install-local.sh
```

---

## Step 6 — Update root `.gitignore`

Add one entry not already covered by the root file:

```gitignore
# cursor-plugin
cursor-plugin/.skene/
```

The rest of the plugin's `.gitignore` (`.DS_Store`, `__pycache__/`, `.env`, `node_modules/`) is already present in the root `.gitignore`.

---

## Step 7 — Update `cursor-plugin/README.md`

The install/uninstall commands are referenced twice. Update them to reflect the new path when running from the repo root:

```diff
-bash scripts/install-local.sh
+bash cursor-plugin/scripts/install-local.sh

-bash scripts/uninstall-local.sh
+bash cursor-plugin/scripts/uninstall-local.sh
```

Also update the **Plugin Structure** section: change the root label from `skene-cursor-plugin/` to `cursor-plugin/`.

---

## Step 8 — Update root `README.md`

Add a `cursor-plugin/` entry to the monorepo overview so it's discoverable. A short line pointing to `cursor-plugin/README.md` is enough.

---

## Step 9 — Commit

```bash
git add .cursor-plugin/
git add cursor-plugin/
git add .gitignore README.md
git commit -m "feat: add cursor-plugin to monorepo"
```

---

## Step 10 — Archive the old repo

Once the migration is merged and the install script verified working:

1. Go to `skene-cursor-plugin` on GitHub
2. Settings → **Archive this repository**

Do not delete it straight away — leave it archived for a few weeks in case anyone has it cloned.

---

## What does NOT need to change

| Item | Reason |
|------|--------|
| `install-local.sh` / `uninstall-local.sh` logic | Self-contained via `dirname`; internal layout unchanged |
| `hooks/hooks.json` script paths | Resolved relative to plugin root by Cursor; internal layout unchanged |
| `commands/`, `skills/`, `rules/` content | All CLI calls use `uvx skene` (system-installed); no hardcoded paths |
| `cursor-plugin/.cursor-plugin/plugin.json` (except `repository`) | No path references |