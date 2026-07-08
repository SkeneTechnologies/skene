# skene

A CLI toolkit for analyzing codebases through the lens of Product-Led Growth (PLG) — mapping the customer journey encoded in your code and database schema.

## What skene does

- **Maps the customer journey** — `analyse-journey` uses parallel code and schema agents to produce a `journey.yaml` of your product's user lifecycle
- **Maintains a feature registry** — persistent tracking of growth features across analysis runs with merge-update semantics
- **Pushes the Skene bundle upstream** — uploads files from the configured output directory plus the latest trigger migration to Skene Cloud
- **Validates engine/migration alignment** — `status` checks action-enabled engine features against generated SQL artifacts
- **Runs as a client/server system** — a backend server (`skene serve`) owns the analysis engine and exposes an [HTTP API](reference/http-api.md); the CLI and TUI are clients, and every run is persisted as a session trace
- **Supports multiple LLM providers**: OpenAI, Gemini, Anthropic, LM Studio, Ollama, and any OpenAI-compatible endpoint

## Core workflow

```bash
# 1. Create a config file
uvx skene config --init

# 2. Set up your LLM provider and API key interactively
uvx skene config

# 3. Analyse your codebase and schema into a journey.yaml
uvx skene analyse-journey .

# 4. Login to Skene Cloud
uvx skene login

# 5. Push artifacts upstream
uvx skene push
```

## Key concepts

**Journey** (`journey.yaml`) — The primary output of the `analyse-journey` command. A validated YAML map of your product's user lifecycle: milestones discovered by parallel code and schema agents, merged and classified into seven canonical lifecycle stages.

**Engine model** (`skene-context/engine.yaml`) — A YAML model that captures subjects and features, including optional action definitions for trigger/runtime behavior.

**Feature registry** (`feature-registry.json`) — A persistent registry of growth features that tracks features across analysis runs. Features are marked active or archived, linked to engine feature keys, and annotated with growth pillars (onboarding, engagement, retention).

**Skene API key** — A single key from Skene Cloud that manages all tokens required to use LLM models and authorizes pushing engine artifacts upstream. One key replaces per-provider API keys for LLM usage and enables cloud push. Get your key at https://www.skene.ai/workspace/apikeys

## Documentation

### Getting started

- [Installation](getting-started/installation.md) — Install via uvx, pip, or from source
- [Quickstart](getting-started/quickstart.md) — End-to-end walkthrough

### Guides

#### Create
- [Push](guides/push.md) — Pushing engine + trigger artifacts upstream

#### Manage
- [Login](guides/login.md) — Authenticating with Skene Cloud upstream
- [Status](guides/status.md) — Checking engine/migration implementation status
- [Features](guides/features.md) — Managing and exporting the feature registry
- [LLM providers](guides/llm-providers.md) — Configuring OpenAI, Gemini, Claude, local LLMs
- [Configuration](guides/configuration.md) — Config files, env vars, and priority

### Reference

- [CLI reference](reference/cli.md) — All commands and flags
- [HTTP API](reference/http-api.md) — The `skene serve` REST + SSE API, domain model, and event stream
- [Python API](reference/python-api.md) — CodebaseExplorer, journey models, schemas

### Help

- [Troubleshooting](troubleshooting.md) — LM Studio, Ollama, common errors
