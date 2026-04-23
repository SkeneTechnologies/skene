# Quickstart

Get from zero to a deployed growth loop.

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

## Analyze, plan, build

### Analyze your codebase

```bash
uvx skene analyze .
```

Scans your codebase and generates files in `./skene/` (legacy projects using `./skene-context/` continue to work):

- **`growth-manifest.json`** -- your tech stack, growth features, and opportunities
- **`growth-template.json`** -- a growth template tailored to your business type
- **`feature-registry.json`** -- tracks features across analysis runs

### Generate a growth plan

```bash
uvx skene plan
```

Produces a prioritized growth plan with executive summary, opportunities, and a technical execution section.

For activation-focused analysis instead of general growth, add `--activation`.

### Build an implementation prompt

```bash
uvx skene build
```

Generates a focused implementation prompt from your growth plan and asks where to send it -- **Cursor**, **Claude**, or **Show** in terminal.

Also updates `skene/engine.yaml` and writes trigger migration SQL to `supabase/migrations/` for action-enabled features.

> **Tip:** Use `--target file` to skip the interactive menu (useful for scripting).

## Verify and deploy

### Check implementation status

After implementing your engine feature plan, verify engine/migration alignment:

```bash
uvx skene status
```

Checks `skene/engine.yaml` structure and verifies action-enabled features have matching migration triggers.

### Push to Supabase and upstream

If your project uses Supabase, build artifacts first and then push upstream:

```bash
uvx skene login --upstream https://skene.ai/workspace/<my-workspace-name>
uvx skene build
uvx skene push
```

## What you get

Your `./skene/` directory contains:

| File | Description |
|---|---|
| `growth-manifest.json` | Tech stack, growth features, opportunities |
| `growth-template.json` | Growth template tailored to your business type |
| `feature-registry.json` | Features tracked across analysis runs, linked to engine features |
| `growth-plan.md` | Prioritized growth plan with technical execution details |
| `implementation-prompt.md` | Ready-to-use prompt for your AI coding assistant |
| `skene/engine.yaml` | Engine model (subjects + features), merged incrementally by `build` |

## Alternative: Quick one-liner

If you want to try the analysis without setting up a config file first, pass your API key inline:

```bash
uvx skene analyze . --api-key "your-key"
```

This uses the default provider (openai) and model (gpt-4o). To use a different provider:

```bash
uvx skene analyze . --api-key "your-key" --provider gemini --model gemini-3-flash-preview
```

## Alternative: Free preview (no API key)

If you want to see what skene does before configuring an LLM, simply run `analyze` without an API key:

```bash
uvx skene analyze .
```

Without an API key (and no local provider), the command falls back to a sample preview showing the kind of output a full analysis produces.

## Next steps

- [Analyze command in depth](../guides/analyze.md) -- all flags, output customization, excluding folders
- [Plan command in depth](../guides/plan.md) -- context directories, activation mode, custom manifest paths
- [Build command in depth](../guides/build.md) -- prompt generation, Cursor/Claude integration
- [Push command in depth](../guides/push.md) -- Supabase migrations and upstream deployment
- [Status command in depth](../guides/status.md) -- growth loop validation and alternative matching
- [Features](../guides/features.md) -- managing and exporting the feature registry
- [Login](../guides/login.md) -- authenticating with Skene Cloud upstream
- [Configuration reference](../guides/configuration.md) -- config files, environment variables, precedence rules
- [LLM providers](../guides/llm-providers.md) -- setup for OpenAI, Gemini, Anthropic, LM Studio, Ollama, and generic endpoints
