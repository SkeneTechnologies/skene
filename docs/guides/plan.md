# Plan Command

The `plan` command generates a strategic growth plan by feeding your manifest and template data to a "Council of Growth Engineers" -- an LLM system prompt that operates as an elite advisory board focused on first-time user activation.

## Prerequisites

Before running `plan`, you need:

- An API key configured for a cloud LLM provider (OpenAI, Gemini, Anthropic), or a local LLM server running (LM Studio, Ollama). See [configuration](configuration.md) for setup instructions.
- Optionally, `growth-manifest.json` and `growth-template.json` from a previous `analyze` run. The plan command works without these files but produces better results when they are available.

## Basic usage

Generate a growth plan using auto-detected context files:

```bash
uvx skene-growth plan
```

The command looks for `growth-manifest.json` and `growth-template.json` in `./skene-context/` (default output from `analyze`), then falls back to the current directory. Neither file is required -- the command runs with whatever context it finds.

Specify context files explicitly:

```bash
uvx skene-growth plan --manifest ./skene-context/growth-manifest.json --template ./skene-context/growth-template.json
```

Point to a directory containing both files:

```bash
uvx skene-growth plan --context ./my-context
```

Generate an activation-focused plan:

```bash
uvx skene-growth plan --activation
```

## Flag reference

> **Note:** The `--activation` flag was previously called `--onboarding` in earlier versions.

| Flag | Short | Description |
|------|-------|-------------|
| `--manifest PATH` | | Path to `growth-manifest.json` |
| `--template PATH` | | Path to `growth-template.json` |
| `--context PATH` | `-c` | Directory containing manifest and template. Auto-detected from `./skene-context/` if not specified. |
| `--output PATH` | `-o` | Output path for growth plan markdown. Default: `./skene-context/growth-plan.md` |
| `--api-key TEXT` | | API key for LLM provider (or `SKENE_API_KEY` env var) |
| `--provider TEXT` | `-p` | LLM provider: `openai`, `gemini`, `anthropic`/`claude`, `lmstudio`, `ollama`, `generic` |
| `--model TEXT` | `-m` | Model name (e.g., `gemini-3-flash-preview`, `claude-sonnet-4-5`) |
| `--base-url TEXT` | | Base URL for OpenAI-compatible API endpoint. Required when provider is `generic`. Also set via `SKENE_BASE_URL` env var or config. |
| `--verbose` | `-v` | Enable verbose output |
| `--activation` | | Generate activation-focused plan using Senior Activation Engineer perspective |
| `--prompt TEXT` | | Additional user prompt to influence the plan generation |
| `--debug` | | Log all LLM input/output to `.skene-growth/debug/` |
| `--no-fallback` | | Disable model fallback on rate limits. Retries the same model with exponential backoff instead of switching to a cheaper model. |

## How it works: the Council of Growth Engineers

The plan command uses a specialized system prompt called the **Council of Growth Engineers**. This is not a generic "give me a plan" prompt. The LLM is instructed to role-play as a council operating at the intersection of product, data, and psychology, drawing on decision-making frameworks from elite growth teams at companies like Meta, Airbnb, and Stripe.

The council follows strict rules:

- **No beginner explanations.** Assumes 99th-percentile competence.
- **No generic growth hacks.** If the advice appears on a "Top 10" list, it is discarded.
- **No hedging.** The council picks the winning path and kills weak strategies immediately.
- **Zero fluff.** Every word must increase signal-to-noise ratio.
- **Focus on first actions.** The plan targets first-time user activation, not long-term retention.
- **No demos or hardcoded data.** Solutions must deliver real configuration paths or incremental real value.

The council generates a structured memo covering eight sections:

1. **Executive Summary** -- High-level overview focused on first-time activation
2. **The CEO's Next Action** -- The single most impactful move to execute in the next 24 hours
3. **Strip to the Core** -- Reframes the problem as a first-action activation challenge
4. **The Playbook** -- Hidden mechanics used by elite growth teams
5. **Engineer the Asymmetric Leverage** -- The one lever that creates 10x activation for 1x input
6. **Apply Power Dynamics** -- Strategy based on controlling onboarding, first value, activation friction, and action clarity
7. **Technical Execution** -- Detailed build plan with confidence scores, exact logic, data triggers, and sequencing
8. **The Memo** -- The complete engineering memo, direct and high-signal

The Technical Execution section is particularly important because it feeds directly into the `build` command.

## Activation mode

The `--activation` flag switches the system prompt from the Council of Growth Engineers to a **Senior Activation Engineer** perspective. This mode focuses specifically on activation optimization with a different philosophy:

```bash
uvx skene-growth plan --activation
```

The activation engineer operates under the principle of **progressive revelation** -- treating onboarding not as a one-time event but as a continuous evolution of state. Key concepts:

- **The 60-Second Rule.** The first minute determines lifetime value. If the user has not felt the impact of value within 60 seconds, the opportunity is lost.
- **Contextual Configuration.** Configuration is friction. Collect information only at the moment of action.
- **Data-Driven Correction.** Onboarding flows drift when the product evolves but the flow remains static.

The activation memo follows a different structure:

1. **Strip to the Momentum Core** -- Distinguish between "tour" (weak) and "pathway to power" (strong)
2. **The Playbook** -- Hidden mechanics from elite onboarding at Stripe, Linear, Vercel
3. **Engineer the Asymmetric Move** -- The single lever that makes the rest of the product inevitable
4. **Apply Power Dynamics** -- Control of the clock, state, configuration, and signals
5. **Technical Execution** -- The onboarding primitive to deploy, with confidence score and exact logic
6. **The "Generic" Trap** -- Why tooltip tours lead to completion without adoption
7. **Your Next Action** -- The most impactful technical move for the next 24 hours
8. **The Memo** -- The engineering memo

## Context files

The plan command auto-detects context files in this order:

1. If `--context` is specified, looks inside that directory first
2. Checks `./skene-context/` (default output directory from `analyze`)
3. Checks the current directory

For the manifest:
- `<context>/growth-manifest.json`
- `./skene-context/growth-manifest.json`
- `./growth-manifest.json`

For the template:
- `<context>/growth-template.json`
- `./skene-context/growth-template.json`
- `./growth-template.json`

The command also loads any existing **growth loop definitions** from `<context>/growth-loops/`. When previous growth loops are found, the council is instructed not to suggest duplicate features and to focus on complementary opportunities instead.

## Output format

The plan is saved as a Markdown file (default: `./skene-context/growth-plan.md`). If the `-o` path points to a directory or has no file extension, the tool appends `growth-plan.md` automatically.

The output includes:

- The full council memo in Markdown format
- An **Implementation Todo List** displayed in the terminal after generation, showing prioritized tasks extracted from the plan

After generation, the terminal displays the memo content and a summary todo list. The plan file is what the `build` command reads to generate implementation prompts.

## What happens without an API key

If no API key is configured and you are not using a local provider (`ollama`, `lmstudio`), the command falls back to a **sample report** preview. To run the full plan generation, provide an API key via any of these methods:

1. `--api-key` flag
2. `SKENE_API_KEY` environment variable
3. `api_key` field in `.skene-growth.config` or `~/.config/skene-growth/config`

## Debug mode

The `--debug` flag logs all LLM input and output to `.skene-growth/debug/`:

```bash
uvx skene-growth plan --debug
```

You can also enable debug mode permanently in your config file:

```toml
debug = true
```

## Next steps

- [Build](build.md) -- Turn your growth plan into an implementation prompt and send it to Cursor or Claude
- [Configuration](configuration.md) -- Set up persistent config so you do not need to pass flags every time
- [LLM Providers](llm-providers.md) -- Detailed setup for each supported provider
