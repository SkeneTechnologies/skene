# CLI Reference

Complete reference for every `skene` command and flag.

For in-depth usage of individual commands, see the [guides](../guides/analyze.md). This page is a lookup reference.

---

## Global Options

| Flag | Description |
|------|-------------|
| `--version`, `-V` | Show version and exit |
| `--help` | Show help message and exit |

When invoked with no arguments, `skene` prints help and exits.

---

## `analyze`

Analyze a codebase and generate `growth-manifest.json`.

Scans your codebase to detect the technology stack, current growth features, and new growth opportunities. Requires an LLM provider (or falls back to a sample preview if no API key is set).

```
skene analyze [PATH] [OPTIONS]
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `PATH` | `.` | Path to codebase directory to analyze (must exist) |

### Options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--output PATH` | `-o` | `./skene-context/growth-manifest.json` (or configured `output_dir`) | Output path for the manifest file. If a directory is given, `growth-manifest.json` is appended automatically. |
| `--api-key TEXT` | | `$SKENE_API_KEY` or config | API key for the LLM provider |
| `--provider TEXT` | `-p` | config value | LLM provider: `openai`, `gemini`, `anthropic` (or `claude`), `lmstudio`, `ollama`, `generic` (aliases: `openai-compatible`, `openai_compatible`) |
| `--model TEXT` | `-m` | provider default | LLM model name (e.g. `gpt-4o`, `gemini-3-flash-preview`) |
| `--base-url TEXT` | | `$SKENE_BASE_URL` or config | Base URL for OpenAI-compatible API endpoint. Required when provider is `generic`. |
| `--quiet` | `-q` | `false` | Suppress output, show errors only |
| `--product-docs` | | `false` | Also generate `product-docs.md` with user-facing feature documentation |
| `--features` | | `false` | Only analyze growth features and update `feature-registry.json` (skips opportunities and revenue leakage) |
| `--exclude TEXT` | `-e` | config value | Folder names to exclude from analysis. Repeatable: `--exclude tests --exclude vendor`. Merged with `exclude_folders` from config. |
| `--debug` | | `false` | Show diagnostic messages and log LLM I/O to `~/.local/state/skene/debug/` |
| `--no-fallback` | | `false` | Disable model fallback on rate limits (429). Retries the same model with exponential backoff instead of switching to a cheaper model. |

### Behavior notes

- When no API key is provided and the provider is not local (`lmstudio`, `ollama`, `generic`), the command falls back to a sample preview.
- Local providers (`lmstudio`, `ollama`, `generic`) do not require an API key.
- The `generic` provider requires `--base-url`.

See the [analyze guide](../guides/analyze.md) for detailed usage.

---

## `plan`

Generate a growth plan using the Council of Growth Engineers methodology.

Reads the manifest and template produced by `analyze`, then uses an LLM to create a prioritized growth plan with implementation tasks.

```
skene plan [OPTIONS]
```

### Options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--manifest PATH` | | auto-detected | Path to `growth-manifest.json`. Auto-detected from `./skene-context/` (or legacy `./skene/`), `./`, or the context directory. |
| `--template PATH` | | auto-detected | Path to `growth-template.json`. Auto-detected using the same search order. |
| `--context PATH` | `-c` | auto-detected | Directory containing manifest and template files. Checked before default paths. |
| `--output PATH` | `-o` | `./skene-context/growth-plan.md` | Output path for the growth plan (markdown). If a directory is given, `growth-plan.md` is appended. |
| `--api-key TEXT` | | `$SKENE_API_KEY` or config | API key for the LLM provider |
| `--provider TEXT` | `-p` | config value | LLM provider: `openai`, `gemini`, `anthropic`/`claude`, `lmstudio`, `ollama`, `generic` |
| `--model TEXT` | `-m` | provider default | LLM model name |
| `--base-url TEXT` | | `$SKENE_BASE_URL` or config | Base URL for OpenAI-compatible API endpoint. Required when provider is `generic`. |
| `--quiet` | `-q` | `false` | Suppress output, show errors only |
| `--activation` | | `false` | Generate an activation-focused plan using a Senior Activation Engineer perspective |
| `--prompt TEXT` | | | Additional user prompt to influence the plan generation |
| `--debug` | | `false` | Show diagnostic messages and log LLM I/O to `~/.local/state/skene/debug/` |
| `--no-fallback` | | `false` | Disable model fallback on rate limits (429). Retries the same model with exponential backoff instead of switching to a cheaper model. |

### Auto-detection order

Both `--manifest` and `--template` are auto-detected by searching these paths in order:

1. `<context>/growth-manifest.json` (if `--context` is set)
2. `./skene-context/growth-manifest.json`
3. `./skene/growth-manifest.json` (legacy)
4. `./growth-manifest.json`

Neither file is strictly required; the plan command works with whatever context is available.

See the [plan guide](../guides/plan.md) for detailed usage.

---

## `build`

Build engine artifacts and an AI-ready implementation prompt from your growth plan.

Extracts the Technical Execution section from the growth plan, updates `skene-context/engine.yaml`, updates `skene-context/feature-registry.json` (or the legacy `skene/feature-registry.json` when the bundle already uses that name), generates Supabase trigger migration SQL (unless skipped), and then offers prompt delivery options (Cursor deep link, Claude CLI, or display).

```
skene build [OPTIONS]
```

### Options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--plan PATH` | | auto-detected | Path to the growth plan markdown file. Auto-detected from `./skene-context/growth-plan.md` (or legacy `./skene/growth-plan.md`) or `./growth-plan.md`. |
| `--context PATH` | `-c` | auto-detected | Directory containing `growth-plan.md` |
| `--api-key TEXT` | | `$SKENE_API_KEY` or config | API key for the LLM provider |
| `--provider TEXT` | `-p` | config value | LLM provider: `openai`, `gemini`, `anthropic`/`claude`, `lmstudio`, `ollama`, `generic` |
| `--model TEXT` | `-m` | provider default | LLM model name |
| `--base-url TEXT` | | `$SKENE_BASE_URL` or config | Base URL for OpenAI-compatible API endpoint. Required when provider is `generic`. |
| `--quiet` | `-q` | `false` | Suppress output, show errors only |
| `--debug` | | `false` | Show diagnostic messages and log LLM I/O to `~/.local/state/skene/debug/` |
| `--no-fallback` | | `false` | Disable model fallback on rate limits (429). Retries the same model with exponential backoff instead of switching to a cheaper model. |
| `--target TEXT` | `-t` | interactive | Skip the interactive menu and send the prompt directly. Options: `cursor`, `claude`, `show`, `file`. |
| `--feature TEXT` | `-f` | | Bias toward this feature name when linking engine features to the registry |
| `--skip-migrations` | | `false` | Skip writing Supabase trigger migration files from actionable engine features |

### Delivery targets

After generating the prompt, an interactive menu asks where to send it:

1. **Cursor** -- opens the prompt via a Cursor deep link
2. **Claude** -- launches the Claude CLI with the prompt file
3. **Show** -- prints the full prompt to the terminal

When `--target` is provided, the interactive menu is skipped entirely. The `file` target saves the prompt to disk and exits without opening any editor or printing the full content. This is the recommended mode for scripting and subprocess usage.

The prompt is always saved to a file in the plan's parent directory regardless of target selection.

### Behavior notes

- Requires a configured LLM (API key + provider). Falls back to a template-based prompt if the LLM call fails.
- Ensures `skene-context/engine.yaml` exists and merges a new LLM-generated engine delta into it.
- Updates `skene-context/feature-registry.json` from engine features (legacy `skene/` location still supported).
- Generates `supabase/migrations/*_skene_triggers.sql` from engine features that include `action` (unless `--skip-migrations` is used).
- Use `--target file` for non-interactive pipelines (e.g. `analyze && plan && build --target file`).

See the [build guide](../guides/build.md) for detailed usage.

---

## `analyse-user-journey`

Compile `user-journey.yaml` from existing `schema.yaml`, `growth-manifest.json`, and `engine.yaml` without re-running the full `analyse-journey` pipeline.

```
skene analyse-user-journey [PATH] [OPTIONS]
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `PATH` | *(omit for `.`)* | Project root. Used for resolving paths and config (sticky `output_dir`). |

### Options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--schema PATH` | `-s` | `./skene-context/schema.yaml` | Path to `schema.yaml` (same default family as `analyse-journey`). |
| `--manifest PATH` | `-M` | `./skene-context/growth-manifest.json` | Path to `growth-manifest.json`. |
| `--engine PATH` | `-e` | `./skene-context/engine.yaml` | Path to `engine.yaml`. |
| `--output PATH` | `-o` | *(next to engine)* | Output path for `user-journey.yaml`. |
| `--api-key TEXT` | | `$SKENE_API_KEY` | LLM API key |
| `--provider TEXT` | `-p` | config | LLM provider |
| `--model TEXT` | `-m` | config | Model name |
| `--base-url TEXT` | | `$SKENE_BASE_URL` | OpenAI-compatible base URL (`generic` provider) |
| `--quiet` | `-q` | `false` | Minimal output |
| `--debug` | | `false` | Verbose / LLM logging |
| `--no-fallback` | | `false` | Disable model fallback on rate limits |

### Behavior notes

- Defaults assume the primary bundle directory **`./skene-context/`** (aligned with `analyse-journey`). Projects that only use legacy **`./skene/`** should pass `--schema`, `--manifest`, and `--engine` explicitly.

---

## `status`

Show implementation status for `skene-context/engine.yaml`.

Loads `skene-context/engine.yaml`, validates structure, and checks whether action-enabled features have matching trigger/function entries in `supabase/migrations/*.sql`.

```
skene status [PATH] [OPTIONS]
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `PATH` | `.` | Path to the project root directory (must exist) |

### Options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--context PATH` | `-c` | | Deprecated. If set to a Skene bundle directory (`skene-context/` or legacy `skene/`), the parent directory is used as project root. |
| `--find-alternatives` | | `false` | Deprecated for engine status checks; currently ignored. |
| `--api-key TEXT` | | `$SKENE_API_KEY` or config | Deprecated for engine status checks; currently ignored. |
| `--provider TEXT` | `-p` | config value | Deprecated for engine status checks; currently ignored. |
| `--model TEXT` | `-m` | provider default | Deprecated for engine status checks; currently ignored. |

### Project root resolution

- Uses `PATH` as project root by default.
- If `--context` points to a Skene bundle directory (`.../skene-context` or `.../skene`), uses the parent directory as project root.

### Behavior notes

- Validates `skene-context/engine.yaml` and checks duplicate keys/required fields.
- For features with `action`, expects matching trigger/function tokens in SQL migrations. The detail column shows the latest matching migration filename; if the same trigger appears in older files, the suffix `(+N)` indicates how many additional matches exist.
- For features without `action`, reports code-only mode (no trigger required).
- Returns non-zero exit code when required engine/migration checks fail.

See the [status guide](../guides/status.md) for detailed usage.

---

## `validate`

Validate a `growth-manifest.json` file against the GrowthManifest schema.

```
skene validate MANIFEST
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `MANIFEST` | Yes | Path to the `growth-manifest.json` file to validate (must exist) |

### Behavior notes

- Parses the file as JSON, then validates it against the Pydantic `GrowthManifest` model.
- On success, prints a summary table showing project name, version, tech stack, and feature counts.
- On failure, prints the validation error and exits with code 1.

---

## `config`

Manage skene configuration files.

```
skene config [OPTIONS]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--init` | `false` | Create a sample `.skene.config` file in the current directory |
| `--show` | `false` | Show current configuration values and exit (no interactive editing) |

### Default behavior (no flags)

When invoked without `--init` or `--show`:

1. Displays current configuration values (same as `--show`)
2. Asks whether you want to edit the configuration
3. If yes, launches an interactive setup flow to select provider, model, and enter an API key

### Configuration load order

Configuration is resolved in this order (later sources override earlier ones):

1. User config: `~/.config/skene/config`
2. Project config: `./.skene.config`
3. Environment variables: `SKENE_API_KEY`, `SKENE_PROVIDER`
4. CLI flags

See the [configuration guide](../guides/configuration.md) for file format and all supported options.

---

## `push`

Upload the Skene bundle (all files under `{output_dir}`) and the latest trigger migration to Skene Cloud.

`push` does not generate migrations. Run `skene build` first so `engine.yaml`, optional `feature-registry.json`, and `supabase/migrations/*_skene_triggers.sql` exist.

```
skene push [PATH] [OPTIONS]
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `PATH` | `.` | Project root. Artifact paths and sticky `output_dir` resolution use this directory (see [configuration](../guides/configuration.md)). |

### Options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--upstream TEXT` | `-u` | config / default cloud | Workspace URL (e.g. `https://skene.ai/workspace/my-app`). Also read from `.skene.config`. |
| `--quiet` | `-q` | `false` | Suppress non-error output. |
| `--debug` | | `false` | Diagnostic messages and LLM debug logging. |

### Behavior notes

- Requires `{output_dir}/engine.yaml` and a trigger migration under `supabase/migrations/` (newest `*_skene_triggers.sql`, or legacy `*skene_trigger*` / `*skene_telemetry*` names).
- Sends a JSON payload with `manifest` and `files` (project-relative paths and file contents) to the upstream `/api/v1/push` API.
- Use `skene login` (or `SKENE_UPSTREAM_API_KEY`) for authentication.

See the [push guide](../guides/push.md) for detailed usage.

---

## `login`

Log in to Skene Cloud upstream for push.

```
skene login [OPTIONS]
```

### Options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--upstream TEXT` | `-u` | | Upstream workspace URL (e.g. `https://skene.ai/workspace/my-app`) |
| `--status` | `-s` | `false` | Show current login status for this project |

### Behavior notes

- Saves upstream URL, workspace, and API key to `.skene.config` with restrictive permissions (`0600`).
- Use `--status` to check whether you are logged in for the current project.

See the [login guide](../guides/login.md) for detailed usage.

---

## `logout`

Log out from upstream (remove saved token).

```
skene logout
```

### Behavior notes

- Removes upstream credentials from `.skene.config`.
- Does not invalidate the token server-side.

---


## `features`

Manage the growth feature registry.

### `features export`

Export the feature registry for use in external tools.

```
skene features export [PATH] [OPTIONS]
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `PATH` | `.` | Project root (to locate the Skene bundle directory) |

### Options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--context PATH` | `-c` | auto-detected | Path to the Skene bundle directory (`skene-context/` or legacy `skene/`) |
| `--format TEXT` | `-f` | `json` | Output format: `json`, `csv`, `markdown` |
| `--output PATH` | `-o` | stdout | Output file path. Prints to stdout if omitted. |

### Behavior notes

- Reads `feature-registry.json` from the context directory.
- Requires running `analyze` first to populate the registry.
- Use for integrating with dashboards, Linear, Notion, or documentation.

See the [features guide](../guides/features.md) for detailed usage.

---

## Environment Variables

| Variable | Used by | Description |
|----------|---------|-------------|
| `SKENE_API_KEY` | `analyze`, `plan`, `build`, `status` | API key for the LLM provider. Equivalent to `--api-key`. |
| `SKENE_BASE_URL` | `analyze`, `plan`, `build` | Base URL for OpenAI-compatible endpoints. Equivalent to `--base-url`. |
| `SKENE_PROVIDER` | config loading | LLM provider override at the environment level. |
| `SKENE_OUTPUT_DIR` | all commands | Override `output_dir` for commands that have no dedicated flag (primarily `push`). |
| `SKENE_UPSTREAM_API_KEY` | `push`, `login` | API key for upstream authentication. |
| `SKENE_DEBUG` | all commands | Enable debug mode (`true`/`false`). |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Error (invalid input, missing API key, validation failure, or deprecated command) |

---

## Examples

```bash
# Full workflow
uvx skene config --init
uvx skene config
uvx skene analyze .
uvx skene plan
uvx skene build

# Analyze with explicit provider settings
uvx skene analyze ./my-app -p gemini -m gemini-3-flash-preview --api-key "YOUR_KEY"

# Analyze with a local LLM (no API key needed)
uvx skene analyze . -p ollama -m llama3

# Analyze with OpenAI-compatible endpoint
uvx skene analyze . -p generic --base-url http://localhost:8080/v1

# Generate activation-focused plan
uvx skene plan --activation

# Validate a manifest
uvx skene validate ./skene-context/growth-manifest.json

# Check engine implementation status
uvx skene status

# Features-only analysis (updates feature registry without full analysis)
uvx skene analyze . --features

# Build engine + trigger artifacts, then push upstream
uvx skene build
uvx skene push
uvx skene push --upstream https://skene.ai/workspace/my-app

# Login/logout from upstream
uvx skene login --upstream https://skene.ai/workspace/my-app
uvx skene login --status
uvx skene logout

# Export feature registry
uvx skene features export --format markdown -o features.md

# Quick preview (no API key, just run analyze without a key)
uvx skene analyze .
```
