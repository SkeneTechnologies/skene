# Plan Command

The `plan` command generates a strategic growth plan from your manifest and template data. It uses an LLM to produce a structured document focused on first-time user activation, leverage mechanics, and technical execution.

## Prerequisites

Before running `plan`, you need:

- An API key configured for a cloud LLM provider (OpenAI, Gemini, Anthropic), or a local LLM server running (LM Studio, Ollama). See [configuration](configuration.md) for setup instructions.
- Optionally, `growth-manifest.json` and `growth-template.json` from a previous `analyze` run. The plan command works without these files but produces better results when they are available.

## Basic usage

Generate a growth plan using auto-detected context files:

```bash
uvx skene plan
```

The command looks for `growth-manifest.json` and `growth-template.json` in `./skene/` first, then the legacy `./skene-context/` directory, then falls back to the current directory. Neither file is required — the command runs with whatever context it finds.

Specify context files explicitly:

```bash
uvx skene plan --manifest ./skene/growth-manifest.json --template ./skene/growth-template.json
```

Point to a directory containing both files:

```bash
uvx skene plan --context ./my-context
```

Generate an activation-focused plan:

```bash
uvx skene plan --activation
```

## Flag reference

> **Note:** The `--activation` flag was previously called `--onboarding` in earlier versions.

| Flag | Short | Description |
|------|-------|-------------|
| `--manifest PATH` | | Path to `growth-manifest.json` |
| `--template PATH` | | Path to `growth-template.json` |
| `--context PATH` | `-c` | Directory containing manifest and template. Auto-detected from `./skene/` (or legacy `./skene-context/`) if not specified. |
| `--output PATH` | `-o` | Output path for growth plan markdown. Default: `./skene/growth-plan.md` |
| `--api-key TEXT` | | API key for LLM provider (or `SKENE_API_KEY` env var) |
| `--provider TEXT` | `-p` | LLM provider: `openai`, `gemini`, `anthropic`/`claude`, `lmstudio`, `ollama`, `generic` |
| `--model TEXT` | `-m` | Model name (e.g., `gemini-3-flash-preview`, `claude-sonnet-4-5`) |
| `--base-url TEXT` | | Base URL for OpenAI-compatible API endpoint. Required when provider is `generic`. Also set via `SKENE_BASE_URL` env var or config. |
| `--quiet` | `-q` | Suppress output, show errors only |
| `--activation` | | Generate activation-focused plan using Senior Activation Engineer perspective |
| `--prompt TEXT` | | Additional user prompt to influence the plan generation |
| `--debug` | | Show diagnostic messages and log LLM I/O to `~/.local/state/skene/debug/` |
| `--no-fallback` | | Disable model fallback on rate limits. Retries the same model with exponential backoff instead of switching to a cheaper model. |

## How the plan process works

The plan is generated in multiple steps:

1. **Executive Summary** — Always first. A high-level summary focused on the growth core and global maximum.
2. **Middle sections** — Configurable. Each section is generated in sequence, with prior sections passed as context for coherence.
3. **Technical Execution** — Always last. Overview with confidence, what we're building, most important technical tasks (short, no phase grouping), data triggers, and success metrics.

The system prompt enforces high signal-to-noise, no generic advice, and utility-first thinking. The Technical Execution section feeds directly into the `build` command.

## How to influence the sections generated

You can shape the plan in three ways:

### 1. `plan-steps.md` — Define custom middle sections

The middle sections (between Executive Summary and Technical Execution) are driven by a `plan-steps.md` file. Place it at `skene/plan-steps.md` (or legacy `skene-context/plan-steps.md`) or in the directory specified by `--context`.

The file can be freeform markdown. The system sends it to the LLM, which interprets your intent and produces structured section definitions. You can use headings, bullet lists, or prose:

```markdown
## The Growth Core
Fundamental analysis. Global Maximum vs local maxima.

## The Playbook (What?)
Invisible Playbook. Moat identification.

## The Average Trap (Why?)
Common Path failure. V/T compounding logic.

## The Mechanics of Leverage (How?)
Four powers: Onboarding, Retention, Virality, Friction.
```

Or a looser style:

```markdown
# My Plan Focus

I want the plan to cover:
- A deep analysis of what the core utility is
- What elite teams would do differently (the invisible playbook)
- Why the common approach fails and the V/T logic
- How to engineer leverage across onboarding, retention, virality
```

If `plan-steps.md` is absent or the LLM cannot parse it, the system falls back to default sections:

1. The Growth Core
2. The Playbook (What?)
3. The Average Trap (Why?)
4. The Mechanics of Leverage (How?)

### 2. `--prompt` — Add context for this run

Use `--prompt` to pass additional instructions that apply to the entire plan:

```bash
uvx skene-growth plan --prompt "Focus on enterprise customers and PLG motion"
```

The prompt is included in the context sent to the LLM for every section.

### 3. Manifest and template — Base context

The manifest (`growth-manifest.json`) and template (`growth-template.json`) provide the core context: tech stack, growth features, opportunities, and lifecycle stages. Richer context yields more specific plans.

## Activation mode

The `--activation` flag switches to a **Senior Activation Engineer** perspective focused on activation optimization:

```bash
uvx skene plan --activation
```

Key concepts:

- **The 60-Second Rule.** The first minute determines lifetime value.
- **Contextual Configuration.** Configuration is friction. Collect information only at the moment of action.
- **Data-Driven Correction.** Onboarding flows drift when the product evolves but the flow remains static.

The activation memo follows a different structure (chapters, risks, scorecard) and is saved as markdown. It does not use the same section framework as the standard growth plan.

## Context files

The plan command auto-detects context files in this order:

1. If `--context` is specified, looks inside that directory first
2. Checks `./skene/` (default output directory from `analyze`)
3. Checks `./skene-context/` (legacy default)
4. Checks the current directory

For the manifest:

- `<context>/growth-manifest.json`
- `./skene/growth-manifest.json`
- `./skene-context/growth-manifest.json`
- `./growth-manifest.json`

For the template:

- `<context>/growth-template.json`
- `./skene/growth-template.json`
- `./skene-context/growth-template.json`
- `./growth-template.json`

The command also loads existing engine context from `<project-root>/skene/engine.yaml` (when present). Existing engine features are used as prior context so the plan focuses on complementary work instead of duplicating what already exists.

## Output format

The plan is saved as a Markdown file (default: `./skene/growth-plan.md`). If the `-o` path points to a directory or has no file extension, the tool appends `growth-plan.md` automatically.

A JSON version (`growth-plan.json`) is saved alongside the markdown for programmatic use. After generation, the terminal displays a summary (section count, todo count, token usage). The plan file is what the `build` command reads to generate implementation prompts.

## What happens without an API key

If no API key is configured and you are not using a local provider (`ollama`, `lmstudio`), the command falls back to a **sample report** preview. To run the full plan generation, provide an API key via any of these methods:

1. `--api-key` flag
2. `SKENE_API_KEY` environment variable
3. `api_key` field in `.skene.config` or `~/.config/skene/config`

## Debug mode

The `--debug` flag shows diagnostic messages on screen and logs all LLM input and output to `~/.local/state/skene/debug/`:

```bash
uvx skene plan --debug
```

You can also enable debug mode permanently in your config file:

```toml
debug = true
```

## Next steps

- [Build](build.md) — Turn your growth plan into an implementation prompt and send it to Cursor or Claude
- [Configuration](configuration.md) — Set up persistent config so you do not need to pass flags every time
- [LLM Providers](llm-providers.md) — Detailed setup for each supported provider
