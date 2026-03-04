# CLI Reference

Complete reference for every `skene-growth` command and flag (version 0.2.1).

For in-depth usage of individual commands, see the [guides](../guides/analyze.md). This page is a lookup reference.

---

## Global Options

| Flag | Description |
|------|-------------|
| `--version`, `-V` | Show version and exit |
| `--help` | Show help message and exit |

When invoked with no arguments, `skene-growth` prints help and exits. The shorthand `skene` (without `-growth`) defaults to the `chat` command instead.

---

## `analyze`

Analyze a codebase and generate `growth-manifest.json`.

Scans your codebase to detect the technology stack, current growth features, and new growth opportunities. Requires an LLM provider (or falls back to a sample preview if no API key is set).

```
skene-growth analyze [PATH] [OPTIONS]
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `PATH` | `.` | Path to codebase directory to analyze (must exist) |

### Options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--output PATH` | `-o` | `./skene-context/growth-manifest.json` | Output path for the manifest file. If a directory is given, `growth-manifest.json` is appended automatically. |
| `--api-key TEXT` | | `$SKENE_API_KEY` or config | API key for the LLM provider |
| `--provider TEXT` | `-p` | config value | LLM provider: `openai`, `gemini`, `anthropic` (or `claude`), `lmstudio`, `ollama`, `generic` (aliases: `openai-compatible`, `openai_compatible`) |
| `--model TEXT` | `-m` | provider default | LLM model name (e.g. `gpt-4o`, `gemini-3-flash-preview`) |
| `--base-url TEXT` | | `$SKENE_BASE_URL` or config | Base URL for OpenAI-compatible API endpoint. Required when provider is `generic`. |
| `--verbose` | `-v` | `false` | Enable verbose output |
| `--product-docs` | | `false` | Also generate `product-docs.md` with user-facing feature documentation |
| `--exclude TEXT` | `-e` | config value | Folder names to exclude from analysis. Repeatable: `--exclude tests --exclude vendor`. Merged with `exclude_folders` from config. |
| `--debug` | | `false` | Log all LLM input/output to `.skene-growth/debug/` |
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
skene-growth plan [OPTIONS]
```

### Options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--manifest PATH` | | auto-detected | Path to `growth-manifest.json`. Auto-detected from `./skene-context/`, `./`, or the context directory. |
| `--template PATH` | | auto-detected | Path to `growth-template.json`. Auto-detected using the same search order. |
| `--context PATH` | `-c` | auto-detected | Directory containing manifest and template files. Checked before default paths. |
| `--output PATH` | `-o` | `./skene-context/growth-plan.md` | Output path for the growth plan (markdown). If a directory is given, `growth-plan.md` is appended. |
| `--api-key TEXT` | | `$SKENE_API_KEY` or config | API key for the LLM provider |
| `--provider TEXT` | `-p` | config value | LLM provider: `openai`, `gemini`, `anthropic`/`claude`, `lmstudio`, `ollama`, `generic` |
| `--model TEXT` | `-m` | provider default | LLM model name |
| `--base-url TEXT` | | `$SKENE_BASE_URL` or config | Base URL for OpenAI-compatible API endpoint. Required when provider is `generic`. |
| `--verbose` | `-v` | `false` | Enable verbose output |
| `--activation` | | `false` | Generate an activation-focused plan using a Senior Activation Engineer perspective |
| `--prompt TEXT` | | | Additional user prompt to influence the plan generation |
| `--debug` | | `false` | Log all LLM input/output to `.skene-growth/debug/` |
| `--no-fallback` | | `false` | Disable model fallback on rate limits (429). Retries the same model with exponential backoff instead of switching to a cheaper model. |

### Auto-detection order

Both `--manifest` and `--template` are auto-detected by searching these paths in order:

1. `<context>/growth-manifest.json` (if `--context` is set)
2. `./skene-context/growth-manifest.json`
3. `./growth-manifest.json`

Neither file is strictly required; the plan command works with whatever context is available.

See the [plan guide](../guides/plan.md) for detailed usage.

---

## `build`

Build an AI-ready implementation prompt from your growth plan, then choose where to send it.

Extracts the Technical Execution section from the growth plan, uses an LLM to generate a focused implementation prompt, and offers interactive delivery options (Cursor deep link, Claude CLI, or display).

```
skene-growth build [OPTIONS]
```

### Options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--plan PATH` | | auto-detected | Path to the growth plan markdown file. Auto-detected from `./skene-context/growth-plan.md` or `./growth-plan.md`. |
| `--context PATH` | `-c` | auto-detected | Directory containing `growth-plan.md` |
| `--api-key TEXT` | | `$SKENE_API_KEY` or config | API key for the LLM provider |
| `--provider TEXT` | `-p` | config value | LLM provider: `openai`, `gemini`, `anthropic`/`claude`, `lmstudio`, `ollama`, `generic` |
| `--model TEXT` | `-m` | provider default | LLM model name |
| `--base-url TEXT` | | `$SKENE_BASE_URL` or config | Base URL for OpenAI-compatible API endpoint. Required when provider is `generic`. |
| `--debug` | | `false` | Log all LLM input/output to `.skene-growth/debug/` |
| `--no-fallback` | | `false` | Disable model fallback on rate limits (429). Retries the same model with exponential backoff instead of switching to a cheaper model. |
| `--target TEXT` | `-t` | interactive | Skip the interactive menu and send the prompt directly. Options: `cursor`, `claude`, `show`, `file`. |

### Delivery targets

After generating the prompt, an interactive menu asks where to send it:

1. **Cursor** -- opens the prompt via a Cursor deep link
2. **Claude** -- launches the Claude CLI with the prompt file
3. **Show** -- prints the full prompt to the terminal

When `--target` is provided, the interactive menu is skipped entirely. The `file` target saves the prompt to disk and exits without opening any editor or printing the full content. This is the recommended mode for scripting and subprocess usage.

The prompt is always saved to a file in the plan's parent directory regardless of target selection.

### Behavior notes

- Requires a configured LLM (API key + provider). Falls back to a template-based prompt if the LLM call fails.
- Also generates and saves a growth loop definition JSON alongside the prompt.
- Use `--target file` for non-interactive pipelines (e.g. `analyze && plan && build --target file`).

See the [build guide](../guides/build.md) for detailed usage.

---

## `status`

Show implementation status of growth loop requirements.

Loads all growth loop JSON definitions from `skene-context/growth-loops/` and uses AST parsing to verify that required files, functions, and patterns are implemented. Displays a report showing which requirements are met and which are missing.

```
skene-growth status [PATH] [OPTIONS]
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `PATH` | `.` | Path to the project root directory (must exist) |

### Options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--context PATH` | `-c` | auto-detected | Path to `skene-context` directory. Auto-detected from `<PATH>/skene-context/` or `./skene-context/`. |
| `--find-alternatives` | | `false` | Use LLM to search for existing functions that might fulfill missing requirements |
| `--api-key TEXT` | | `$SKENE_API_KEY` or config | API key for the LLM provider. Required when `--find-alternatives` is set. |
| `--provider TEXT` | `-p` | config value | LLM provider: `openai`, `gemini`, `anthropic`, `ollama` |
| `--model TEXT` | `-m` | provider default | LLM model name |

### Context auto-detection

When `--context` is not specified, the command checks these paths in order:

1. `<PATH>/skene-context/` (where `PATH` is the positional argument)
2. `./skene-context/`

The directory must contain a `growth-loops/` subdirectory with at least one JSON file.

### Behavior notes

- Validates every growth loop JSON file found in `<context>/growth-loops/`.
- Uses Python AST parsing to verify function and class definitions, import statements, and content patterns.
- With `--find-alternatives`, extracts all functions from the codebase and uses the LLM to find semantic matches for missing requirements (confidence threshold: 60%).
- Does not require an API key unless `--find-alternatives` is enabled.

See the [status guide](../guides/status.md) for detailed usage.

---

## `chat`

Interactive terminal chat with access to skene-growth analysis tools.

```
skene-growth chat [PATH] [OPTIONS]
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `PATH` | `.` | Path to codebase directory |

### Options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--api-key TEXT` | | `$SKENE_API_KEY` or config | API key for the LLM provider |
| `--provider TEXT` | `-p` | config value | LLM provider: `openai`, `gemini`, `anthropic`/`claude`, `lmstudio`, `ollama`, `generic` |
| `--model TEXT` | `-m` | provider default | LLM model name |
| `--base-url TEXT` | | `$SKENE_BASE_URL` or config | Base URL for OpenAI-compatible API endpoint. Required when provider is `generic`. |
| `--max-steps INT` | | `4` | Maximum number of tool calls the LLM can make per user request |
| `--tool-output-limit INT` | | `4000` | Maximum characters of tool output kept in conversation context |
| `--debug` | | `false` | Log all LLM input/output to `.skene-growth/debug/` |

### Behavior notes

- When using the `skene` shorthand (not `skene-growth`), running without a subcommand defaults to `chat`.
- Requires an API key unless using a local provider.

See the [chat guide](../guides/chat.md) for detailed usage.

---

## `validate`

Validate a `growth-manifest.json` file against the GrowthManifest schema.

```
skene-growth validate MANIFEST
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

Manage skene-growth configuration files.

```
skene-growth config [OPTIONS]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--init` | `false` | Create a sample `.skene-growth.config` file in the current directory |
| `--show` | `false` | Show current configuration values and exit (no interactive editing) |

### Default behavior (no flags)

When invoked without `--init` or `--show`:

1. Displays current configuration values (same as `--show`)
2. Asks whether you want to edit the configuration
3. If yes, launches an interactive setup flow to select provider, model, and enter an API key

### Configuration load order

Configuration is resolved in this order (later sources override earlier ones):

1. User config: `~/.config/skene-growth/config`
2. Project config: `./.skene-growth.config`
3. Environment variables: `SKENE_API_KEY`, `SKENE_PROVIDER`
4. CLI flags

See the [configuration guide](../guides/configuration.md) for file format and all supported options.

---

## `generate` (deprecated)

This command is deprecated and will be removed. Use `analyze --product-docs` instead.

```
skene-growth generate [OPTIONS]
```

| Flag | Short | Description |
|------|-------|-------------|
| `--manifest PATH` | `-m` | Path to `growth-manifest.json` |
| `--output PATH` | `-o` | Output directory (default: `./skene-docs`) |

The command prints a deprecation warning and exits with code 1.

---

## Environment Variables

| Variable | Used by | Description |
|----------|---------|-------------|
| `SKENE_API_KEY` | `analyze`, `plan`, `build`, `chat`, `status` | API key for the LLM provider. Equivalent to `--api-key`. |
| `SKENE_BASE_URL` | `analyze`, `plan`, `build`, `chat` | Base URL for OpenAI-compatible endpoints. Equivalent to `--base-url`. |
| `SKENE_PROVIDER` | config loading | LLM provider override at the environment level. |

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
uvx skene-growth config --init
uvx skene-growth config
uvx skene-growth analyze .
uvx skene-growth plan
uvx skene-growth build

# Analyze with explicit provider settings
uvx skene-growth analyze ./my-app -p gemini -m gemini-3-flash-preview --api-key "YOUR_KEY"

# Analyze with a local LLM (no API key needed)
uvx skene-growth analyze . -p ollama -m llama3

# Analyze with OpenAI-compatible endpoint
uvx skene-growth analyze . -p generic --base-url http://localhost:8080/v1

# Generate activation-focused plan
uvx skene-growth plan --activation

# Validate a manifest
uvx skene-growth validate ./skene-context/growth-manifest.json

# Interactive chat
uvx skene-growth chat . -p openai -m gpt-4o

# Check growth loop implementation status
uvx skene-growth status

# Check status with LLM-powered alternative matching
uvx skene-growth status --find-alternatives --api-key "YOUR_KEY"

# Quick preview (no API key, just run analyze without a key)
uvx skene-growth analyze .
```
