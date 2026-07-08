# Push Command

The `push` command uploads your Skene bundle (files under the configured output directory) plus the latest Supabase trigger migration to Skene Cloud.

`push` does not generate anything. It uploads existing artifacts: `engine.yaml`, the optional feature registry, and trigger migrations must already exist.

## Prerequisites

Before running `push`, you need:

- **`{output_dir}/engine.yaml`** — typically `skene-context/engine.yaml` (see [configuration](configuration.md) for `output_dir`).
- **`supabase/migrations/`** containing at least one eligible trigger migration (newest `*_skene_triggers.sql` is used; older repos may use `*skene_trigger*` / `*skene_telemetry*` patterns).

**Configuration:** `output_dir` comes from `.skene.config`, `SKENE_OUTPUT_DIR`, or sticky detection (see [configuration](configuration.md)). Sticky bundle layout is resolved against the **`PATH` you pass to `push`**, not only your current shell directory.

**Auth:** `skene login` or `SKENE_UPSTREAM_API_KEY` for upstream API calls.

## Basic usage

From the project root:

```bash
uvx skene push
```

Target another directory:

```bash
uvx skene push /path/to/project
```

With an explicit upstream (otherwise uses config / default Skene Cloud):

```bash
uvx skene push --upstream https://skene.ai/workspace/my-app
```

## Flag reference

| Flag | Short | Description |
|------|-------|-------------|
| `PATH` | | Project root (default: `.`). Used for artifact paths and sticky `output_dir` resolution. |
| `--upstream TEXT` | `-u` | Workspace URL (e.g. `https://skene.ai/workspace/my-app`). Can also live in `.skene.config`. |
| `--quiet` | `-q` | Suppress non-error output. |
| `--debug` | | Diagnostic messages and LLM debug logging path. |

## How it works

1. **Preflight** — Verifies `engine.yaml` exists under the resolved output directory and that a trigger migration exists under `supabase/migrations/`. Exits with errors if not.
2. **Payload** — Builds a manifest and a `files` list: **all files** under the bundle directory (`output_dir`), plus the latest trigger SQL, each as `{ "path", "content" }` relative to the project root. Missing optional files (for example `feature-registry.json`) are simply omitted from the upload.
3. **API** — `POST` to Skene Cloud `/api/v1/push` with `{ "manifest", "files" }`. Success responses include `artifact_count`, `updated_paths`, and `push_id` where applicable.

## Publishing a journey from the TUI

Running journey analysis (from the TUI or the CLI) never publishes anything by itself — the journey reaches Skene Cloud only when you push. In the TUI that is the explicit **"Deploy to Skene Cloud"** step, which runs a normal `skene push` and uploads the full bundle (engine, registry, migrations, journey) as described above.

## Upstream authentication

```bash
uvx skene login --upstream https://skene.ai/workspace/my-app
```

Upstream URL resolution: `--upstream` → `upstream` in `.skene.config` → default hosted API when unset.

## Next steps

- [Login](login.md) — Authenticate with Skene Cloud
- [Status](status.md) — Validate engine vs migrations
- [Configuration](configuration.md) — `output_dir` and sticky bundles
- [CLI Reference](../reference/cli.md) — All commands
