# CLI Reference

Complete reference for every `skene` command and flag.

For in-depth usage of individual commands, see the [guides](../guides/push.md). This page is a lookup reference.

---

## Global Options

| Flag | Description |
|------|-------------|
| `--version`, `-V` | Show version and exit |
| `--help` | Show help message and exit |

When invoked with no arguments, `skene` prints help and exits.

---

## `analyse-journey`

Generate a `journey.yaml` describing the user lifecycle of a product.

A main "skene" agent orchestrates two parallel subagents — one analyzing the codebase filesystem, one analyzing the database schema — to discover user-facing milestones; a deterministic finalize step merges and classifies them into a validated Customer Journey map across seven lifecycle stages: discovery, onboarding, activation, engagement, retention, expansion, and virality.

By default the command runs an embedded (in-process) server; after [`skene attach`](#attach) (or with `--server`) it drives a remote [`skene serve`](#serve) instance instead. Every run — local or remote — persists a session trace in the [skene database](#serve), which is the debug trail for a run.

```
skene analyse-journey [PATH] [OPTIONS]
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `PATH` | `.` | Path to codebase directory to analyse (omit for current directory) |

### Options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--schema-dir PATH` | | | Directory of pre-exported `*.sql` files for the schema agent |
| `--db-url TEXT` | | | PostgreSQL connection string for live schema introspection (alternative to `--schema-dir`; also `SKENE_DB_URL` env var) |
| `--output PATH` | `-o` | `./skene-context/journey.yaml` | Output path for `journey.yaml` |
| `--product-name TEXT` | | | Product name in the output (default: inferred from repo directory name, DB name, or schema dir name) |
| `--api-key TEXT` | | `$SKENE_API_KEY` or config | API key for the LLM provider |
| `--provider TEXT` | `-p` | config value | LLM provider: `openai`, `gemini`, `anthropic`/`claude`, `lmstudio`, `ollama`, `generic`, `skene` |
| `--model TEXT` | `-m` | provider default | LLM model name |
| `--base-url TEXT` | | `$SKENE_BASE_URL` or config | Base URL for API endpoint |
| `--server TEXT` | | `$SKENE_SERVER_URL`, or the URL saved by `skene attach` | Run the analysis on a remote `skene serve` instance instead of the embedded server. See [Remote mode](#remote-mode) below. |
| `--server-token TEXT` | | `$SKENE_SERVER_TOKEN`, or the token saved by `skene attach` | Bearer token for the remote server |
| `--schema-max-turns INT` | | `150` | Maximum agent turns for the schema agent (range: 1–500) |
| `--code-max-turns INT` | | `200` | Maximum agent turns for the code agent (range: 1–500) |
| `--classify-concurrency INT` | | `8` | Parallel classifier requests (range: 1–64) |
| `--no-specialize` | | `false` | Skip stage specialization; use canonical stage vocabulary |
| `--quiet` | `-q` | `false` | Suppress status messages; show only errors and final results |
| `--debug` | | `false` | Show diagnostic messages and log all LLM input/output |
| `--no-fallback` | | `false` | Disable model fallback on rate limits; retry same model instead |

### Schema sources

The schema agent requires one of two inputs — **never both**:

- **SQL files** (`--schema-dir`): Provide a directory of pre-exported `*.sql` files defining tables, views, constraints, and indexes.
- **Live database** (`--db-url`): Connect directly to a running PostgreSQL database. Skene introspects all user-defined schemas at runtime (excluding `pg_catalog`, `information_schema`, `pg_toast`, and any schema prefixed with `pg_`). Credentials are never stored.

`--schema-dir` and `--db-url` are mutually exclusive. At least one of `PATH`, `--schema-dir`, or `--db-url` must be provided. When `PATH` is omitted, only the schema agent runs (no code agent).

### Remote mode

When a server URL is set — via `--server`, `SKENE_SERVER_URL`, or a prior `skene attach` — the analysis runs on that server instead of in-process:

- No local LLM credentials are needed; the server uses its own LLM configuration (`--api-key`/`--provider`/`--model`/`--base-url` are not forwarded).
- Progress streams live from the server, and `Ctrl-C` aborts the remote run.
- **Paths (`PATH`, `--schema-dir`, `--output`) are interpreted on the server's filesystem**, not the client's.

### Behavior notes

- In local (embedded) mode, requires a configured LLM (API key + provider). Local providers (`lmstudio`, `ollama`, `generic`) do not require an API key.
- The `generic` provider requires `--base-url`.
- When `--db-url` is used without `--product-name`, the database name is extracted from the connection string for the product name.
- `--db-url` credentials are used live and never persisted; anything stored or streamed shows a redacted form.
- Every run persists a session trace (agent turns, tool calls, milestones) in the skene database — use it to debug a run. See [`serve`](#serve) for the database location.

See the CLI help output (`skene analyse-journey --help`) for detailed usage.

---

## `serve`

Run the skene backend server headless.

The server owns the analysis engine: it exposes the [HTTP API](http-api.md) (sessions, SSE event stream, journey analysis), and persists every run as a session tree in a global SQLite database. The CLI and the TUI are clients of this server.

```
skene serve [OPTIONS]
```

### Options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--host TEXT` | | `127.0.0.1` | Interface to bind. Binding any non-localhost interface requires `--token`. |
| `--port INT` | | `4906` | Port to listen on |
| `--token TEXT` | | `$SKENE_SERVER_TOKEN` | Bearer token clients must send as `Authorization: Bearer <token>`. Required for non-localhost binds. |
| `--db-path PATH` | | `$SKENE_DB_PATH` or `~/.local/share/skene/skene.db` | Path to the SQLite session database |
| `--api-key TEXT` | | `$SKENE_API_KEY` or config | API key for the LLM provider |
| `--provider TEXT` | `-p` | config value | LLM provider |
| `--model TEXT` | `-m` | provider default | LLM model name |
| `--base-url TEXT` | | `$SKENE_BASE_URL` or config | Base URL for OpenAI-compatible endpoints |
| `--quiet` | `-q` | `false` | Suppress output, show errors only |
| `--debug` | | `false` | Show diagnostic messages |

### Behavior notes

- `/health` is always unauthenticated; all other routes require the bearer token when one is set.
- The server starts fine without LLM credentials — analyse requests then return `503` with the reason.
- LLM configuration is resolved once at startup; changing it means restarting the server (there is deliberately no config-mutation API).
- The session database is global (one per machine, all workspaces) and currently keeps everything — there is no GC command yet.
- Auth is single-tenant: one optional token per server. Multi-tenancy is out of scope.

See the [HTTP API reference](http-api.md) for routes, the event stream, and the domain model.

---

## `attach`

Attach the CLI to a running `skene serve` instance.

```
skene attach <URL> [--token TEXT]
skene attach --clear
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `URL` | Yes (unless `--clear`) | Base URL of the server, e.g. `http://127.0.0.1:4906` |

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--token TEXT` | `$SKENE_SERVER_TOKEN` | Bearer token for the server, if it requires one |
| `--clear` | `false` | Detach: remove the saved server settings (mutually exclusive with `URL`) |

### Behavior notes

- Verifies the server by calling `GET /health` before saving anything.
- Persists `server_url` and `server_token` into `.skene.config` — the project config if one exists (found by walking up from the current directory), otherwise the user config (`~/.config/skene/config`).
- Once attached, `analyse-journey` runs on that server (see [Remote mode](#remote-mode)). Use `--clear` to go back to embedded runs.

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

`push` does not generate migrations. It uploads existing artifacts: `engine.yaml`, optional `feature-registry.json`, and `supabase/migrations/*_skene_triggers.sql` must already exist.

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
- The registry is populated by analysis runs; it must exist before exporting.
- Use for integrating with dashboards, Linear, Notion, or documentation.

See the [features guide](../guides/features.md) for detailed usage.

---

## Environment Variables

| Variable | Used by | Description |
|----------|---------|-------------|
| `SKENE_API_KEY` | `analyse-journey`, `serve` | API key for the LLM provider. Equivalent to `--api-key`. |
| `SKENE_BASE_URL` | `analyse-journey`, `serve` | Base URL for OpenAI-compatible endpoints. Equivalent to `--base-url`. |
| `SKENE_PROVIDER` | config loading | LLM provider override at the environment level. |
| `SKENE_OUTPUT_DIR` | all commands | Override `output_dir` for commands that have no dedicated flag (primarily `push`). |
| `SKENE_UPSTREAM_API_KEY` | `push`, `login` | API key for upstream authentication. |
| `SKENE_DEBUG` | all commands | Enable debug mode (`true`/`false`). |
| `SKENE_DB_URL` | `analyse-journey` | PostgreSQL connection string for live schema introspection. Equivalent to `--db-url`. |
| `SKENE_SERVER_URL` | `analyse-journey` | URL of a remote `skene serve` instance. Equivalent to `--server`. |
| `SKENE_SERVER_TOKEN` | `serve`, `attach`, `analyse-journey` | Bearer token for server auth. Equivalent to `--token` / `--server-token`. |
| `SKENE_DB_PATH` | `serve`, `analyse-journey` | Path to the global SQLite session database. Equivalent to `serve --db-path`. |

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
uvx skene analyse-journey .

# Analyse user journey with SQL schema files
uvx skene analyse-journey ./my-app --schema-dir ./schemas

# Analyse user journey with a live database
uvx skene analyse-journey --db-url "postgresql://user:pass@localhost:5432/mydb"

# Journey analysis with custom output
uvx skene analyse-journey ./my-app --schema-dir ./schemas -o ./output/journey.yaml

# Journey analysis with explicit provider settings
uvx skene analyse-journey . -p gemini -m gemini-3-flash-preview --api-key "YOUR_KEY"

# Journey analysis with a local LLM (no API key needed)
uvx skene analyse-journey . -p ollama -m llama3

# Check engine implementation status
uvx skene status

# Push artifacts upstream
uvx skene push
uvx skene push --upstream https://skene.ai/workspace/my-app

# Login/logout from upstream
uvx skene login --upstream https://skene.ai/workspace/my-app
uvx skene login --status
uvx skene logout

# Export feature registry
uvx skene features export --format markdown -o features.md

# Run the backend server headless (localhost)
uvx skene serve --port 4906

# Serve on all interfaces (token required)
uvx skene serve --host 0.0.0.0 --token "my-secret"

# Attach the CLI to a running server, then analyse remotely
uvx skene attach http://127.0.0.1:4906
uvx skene analyse-journey .          # now runs on the attached server
uvx skene attach --clear             # back to embedded runs
```
