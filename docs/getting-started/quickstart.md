# Quickstart

Get from zero to a customer journey map.

> **Prerequisites**
>
> - Python 3.11 or later
> - [uv](https://docs.astral.sh/uv/) installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
> - An API key from OpenAI, Google Gemini, or Anthropic -- OR a local LLM running via [LM Studio](https://lmstudio.ai/) or [Ollama](https://ollama.com/)

## Setup

### Create and configure

```bash
# Create a config file with sensible defaults
uvx skene config --init

# Set up your LLM provider and API key interactively
uvx skene config
```

The interactive setup walks you through provider, model, and API key selection.

> **Tip:** You can skip config setup entirely by passing `--api-key` and `--provider` flags directly to each command, or by setting the `SKENE_API_KEY` and `SKENE_PROVIDER` environment variables.

## Analyse your journey

### Run the analysis

```bash
uvx skene analyse-journey .
```

A main "skene" agent orchestrates two parallel subagents -- one analyzing your codebase, one analyzing your database schema -- to discover user-facing milestones. A deterministic finalize step merges and classifies them into a validated Customer Journey map across seven lifecycle stages: discovery, onboarding, activation, engagement, retention, expansion, and virality.

The result is written to `./skene-context/journey.yaml`.

### Include your database schema

The schema agent needs one of two inputs -- never both:

```bash
# SQL files: a directory of pre-exported *.sql files
uvx skene analyse-journey . --schema-dir ./schemas

# Live database: a PostgreSQL connection string (credentials are never stored)
uvx skene analyse-journey . --db-url "postgresql://user:pass@localhost:5432/mydb"
```

> **Tip:** Use `-o` to change the output path (default `./skene-context/journey.yaml`) and `--product-name` to override the inferred product name.

## Verify and deploy

### Check implementation status

If your project has a `skene-context/engine.yaml`, verify engine/migration alignment:

```bash
uvx skene status
```

Checks `skene-context/engine.yaml` structure and verifies action-enabled features have matching migration triggers.

### Push upstream

To deploy your Skene bundle to Skene Cloud, log in and push:

```bash
uvx skene login --upstream https://skene.ai/workspace/<my-workspace-name>
uvx skene push
```

> **Note:** Journey analysis never publishes anything by itself. To get your `journey.yaml` into the cloud Customer Journey canvas, push it — from the TUI use the explicit **"Deploy to Skene Cloud"** step, from the CLI run `skene push`. `push` uploads existing artifacts (`engine.yaml`, optional `feature-registry.json`, and the latest trigger migration under `supabase/migrations/`); it does not generate them.

## What you get

Your `./skene-context/` directory contains:

| File | Description |
|---|---|
| `journey.yaml` | Customer journey map across seven lifecycle stages, produced by `analyse-journey` |
| `engine.yaml` | Engine model (subjects + features), validated by `status` and uploaded by `push` |
| `feature-registry.json` | Features tracked across analysis runs, linked to engine features |

## Alternative: Quick one-liner

If you want to try the analysis without setting up a config file first, pass your API key inline:

```bash
uvx skene analyse-journey . --api-key "your-key"
```

This uses the default provider (openai) and model (gpt-4o). To use a different provider:

```bash
uvx skene analyse-journey . --api-key "your-key" --provider gemini --model gemini-3-flash-preview
```

Local providers need no API key at all:

```bash
uvx skene analyse-journey . --provider ollama --model llama3.3
```

## Next steps

- [CLI reference](../reference/cli.md) -- every `analyse-journey` flag, plus `serve`, `attach`, and more
- [Push command in depth](../guides/push.md) -- Supabase migrations and upstream deployment
- [Status command in depth](../guides/status.md) -- engine/migration validation
- [Features](../guides/features.md) -- managing and exporting the feature registry
- [Login](../guides/login.md) -- authenticating with Skene Cloud upstream
- [Configuration reference](../guides/configuration.md) -- config files, environment variables, precedence rules
- [LLM providers](../guides/llm-providers.md) -- setup for OpenAI, Gemini, Anthropic, LM Studio, Ollama, and generic endpoints
