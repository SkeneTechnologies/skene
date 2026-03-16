# Analyze Command

The `analyze` command scans a codebase to detect its technology stack, identify existing growth features, surface growth opportunities, and flag revenue leakage -- all powered by an LLM of your choice.

## Prerequisites

Before running `analyze`, you need one of the following:

- An API key configured for a cloud LLM provider (OpenAI, Gemini, Anthropic). See [configuration](configuration.md) for setup instructions.
- A local LLM server running (LM Studio, Ollama). No API key required.

## Basic usage

Analyze the current directory:

```bash
uvx skene analyze .
```

Analyze a specific project path:

```bash
uvx skene analyze ./my-project
```

Save the manifest to a custom location:

```bash
uvx skene analyze . -o ./output/manifest.json
```

If no API key is configured and you are not using a local provider, the command displays a sample growth analysis preview instead of running a full LLM-powered analysis.

## Flag reference

| Flag | Short | Description |
|------|-------|-------------|
| `PATH` | | Path to codebase (default: `.`, must be an existing directory) |
| `--output PATH` | `-o` | Output path for `growth-manifest.json` |
| `--api-key TEXT` | | API key for LLM provider (or `SKENE_API_KEY` env var) |
| `--provider TEXT` | `-p` | LLM provider: `openai`, `gemini`, `anthropic`/`claude`, `lmstudio`, `ollama`, `generic` (aliases: `openai-compatible`, `openai_compatible`) |
| `--model TEXT` | `-m` | Model name (e.g., `gpt-4o`, `gemini-3-flash-preview`, `claude-sonnet-4-5`) |
| `--base-url TEXT` | | Base URL for OpenAI-compatible endpoint (required for `generic` provider; also `SKENE_BASE_URL` env var) |
| `--product-docs` | | Generate `product-docs.md` with user-facing feature documentation (creates v2.0 manifest) |
| `--features` | | Only analyze growth features and update `feature-registry.json` (skips opportunities and revenue leakage) |
| `--exclude TEXT` | `-e` | Folder names to exclude from analysis (repeatable). Also configurable in `.skene.config` as `exclude_folders`. |
| `--quiet` | `-q` | Suppress output, show errors only |
| `--debug` | | Show diagnostic messages and log LLM I/O to `~/.local/state/skene/debug/` |
| `--no-fallback` | | Disable model fallback on rate limits. Retries the same model with exponential backoff instead of switching to a cheaper model. |

## Output files

By default, output files are saved to `./skene-context/`. You can override this with the `-o` flag. If the `-o` path points to a directory or has no file extension, the tool appends `growth-manifest.json` automatically.

### growth-manifest.json

The primary output. Contains the full analysis results as structured JSON:

| Field | Description |
|-------|-------------|
| `version` | Schema version (`"1.0"` or `"2.0"` with `--product-docs`) |
| `project_name` | Name of the analyzed project |
| `description` | Brief project description |
| `tech_stack` | Detected stack: `framework`, `language`, `database`, `auth`, `deployment`, `package_manager`, `services` |
| `industry` | Inferred industry vertical with `primary`, `secondary` tags, `confidence` score, and `evidence` |
| `current_growth_features` | Features with growth potential, including file paths, detected intent, confidence scores, and growth suggestions |
| `growth_opportunities` | Missing features that could drive growth, with priority levels |
| `revenue_leakage` | Revenue leakage issues with impact assessment and recommendations |
| `generated_at` | ISO 8601 timestamp of when the manifest was generated |

### feature-registry.json

A persistent registry of growth features maintained across analysis runs. Each analysis merges new features into the existing registry: new features are added with `first_seen_at`, matched features are updated with `last_seen_at` and marked `active`, and unmatched features are marked `archived`. The registry also maps features to growth loops via `loop_ids` and annotates them with growth pillars.

See the [features guide](features.md) for registry structure and export options.

### growth-template.json

A custom PLG growth template generated alongside the manifest. Contains lifecycle stages tailored to your project's business type and industry. This template is used by the `plan` command to generate actionable growth plans.

### product-docs.md (only with --product-docs)

A Markdown file containing user-facing product documentation generated from your codebase. See the [Product docs mode](#product-docs-mode) section below.

## Product docs mode

The `--product-docs` flag enables an extended analysis that generates user-facing documentation from your codebase:

```bash
uvx skene analyze . --product-docs
```

When enabled, the command:

1. Collects product overview information (tagline, value proposition, target audience)
2. Identifies user-facing features with descriptions, usage examples, and categories
3. Generates `product-docs.md` in the output directory
4. Produces a v2.0 manifest (extends the standard manifest with `product_overview` and `features` fields)

The v2.0 manifest is a superset of v1.0 -- all standard fields remain present.

## Features-only mode

The `--features` flag runs a lightweight analysis that only updates the feature registry:

```bash
uvx skene analyze . --features
```

This mode:

1. Runs the growth features analyzer only (skips opportunities and revenue leakage)
2. Loads existing growth loops from `skene-context/growth-loops/`
3. Maps loops to features and updates `feature-registry.json`
4. Enriches the manifest with `loop_ids` and `growth_pillars`

This is faster than a full analysis and useful when you want to refresh the feature registry after building new growth loops.

## Excluding folders

Use `--exclude` (or `-e`) to skip folders during analysis. This is useful for large repositories where you want to ignore generated code, vendored dependencies, or test fixtures.

The flag can be used multiple times:

```bash
uvx skene analyze . --exclude node_modules --exclude dist --exclude .next
```

You can also set exclusions permanently in your config file. In `.skene.config`:

```toml
exclude_folders = ["node_modules", "dist", ".next", "vendor", "__pycache__"]
```

CLI exclusions and config exclusions are merged (deduplicated). CLI flags do not override config -- they add to the list.

## Debug mode

The `--debug` flag shows diagnostic messages on screen and logs all LLM input and output to `~/.local/state/skene/debug/`:

```bash
uvx skene analyze . --debug
```

This is useful for:

- Troubleshooting unexpected analysis results
- Inspecting the prompts sent to the LLM
- Verifying that the LLM is receiving the right context

You can also enable debug mode permanently in your config file:

```toml
debug = true
```

Or via environment variable:

```bash
export SKENE_DEBUG=true
```

## Provider-specific examples

### OpenAI

```bash
uvx skene analyze . --provider openai --api-key "sk-..." --model gpt-4o
```

### Google Gemini

```bash
uvx skene analyze . --provider gemini --api-key "AI..." --model gemini-3-flash-preview
```

### Anthropic

```bash
uvx skene analyze . --provider anthropic --api-key "sk-ant-..." --model claude-sonnet-4-5
```

### Ollama (local)

```bash
# Start Ollama first, then:
uvx skene analyze . --provider ollama --model llama3.3
```

No API key required. The default model for Ollama is `llama3.3`.

### LM Studio (local)

```bash
# Start LM Studio server first, then:
uvx skene analyze . --provider lmstudio
```

No API key required.

### Generic / OpenAI-compatible

For any OpenAI-compatible API endpoint:

```bash
uvx skene analyze . \
  --provider generic \
  --base-url "http://localhost:8080/v1" \
  --model my-model
```

The `--base-url` flag is required when using the `generic` or `openai-compatible` provider. You can also set it via the `SKENE_BASE_URL` environment variable.

## What happens without an API key

If no API key is configured and you are not using a local provider (`lmstudio`, `ollama`, `generic`), the command falls back to a **sample report** -- a preview of the analysis output structure using representative data. This lets you see what a full analysis looks like before committing to an API key.

To run the full analysis, provide an API key via any of these methods:

1. `--api-key` flag
2. `SKENE_API_KEY` environment variable
3. `api_key` field in `.skene.config` or `~/.config/skene/config`

## Next steps

- [Plan](plan.md) -- Generate a growth plan from your manifest using the Council of Growth Engineers
- [Features](features.md) -- Export and manage the feature registry
- [Configuration](configuration.md) -- Set up persistent config so you do not need to pass flags every time
