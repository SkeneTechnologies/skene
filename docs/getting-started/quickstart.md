# Quickstart

Get from zero to a full growth plan in six commands.

> **Prerequisites**
>
> - Python 3.11 or later
> - [uv](https://docs.astral.sh/uv/) installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
> - An API key from OpenAI, Google Gemini, or Anthropic -- OR a local LLM running via [LM Studio](https://lmstudio.ai/) or [Ollama](https://ollama.com/)

## The 6-step workflow

### Step 1: Create a config file

```bash
uvx skene-growth config --init
```

This creates `.skene-growth.config` in your current directory with sensible defaults. The file is created with restrictive permissions (`0600` on Unix) since it will hold your API key.

### Step 2: Configure your LLM provider

```bash
uvx skene-growth config
```

This shows your current configuration, then asks if you want to edit it. If you choose to edit, an interactive setup walks you through:

1. **Provider** -- choose from openai, gemini, anthropic, lmstudio, ollama, or generic (any OpenAI-compatible endpoint)
2. **Model** -- pick from a curated list per provider, or enter a custom model name
3. **Base URL** -- only prompted if you select the `generic` provider
4. **API key** -- entered as a password field (hidden input)

The configuration is saved back to your `.skene-growth.config` file.

> **Tip:** You can skip this step entirely by passing `--api-key` and `--provider` flags directly to each command, or by setting the `SKENE_API_KEY` and `SKENE_PROVIDER` environment variables.

### Step 3: Analyze your codebase

```bash
uvx skene-growth analyze .
```

This scans your codebase and generates two files in `./skene-context/`:

- **`growth-manifest.json`** -- structured data about your tech stack, existing growth features, and growth opportunities
- **`growth-template.json`** -- a business-type-aware growth template with prioritized recommendations

The analysis uses your configured LLM to understand your codebase structure, detect the technology stack (framework, language, database, hosting), identify existing growth features, and surface new growth opportunities.

You can pass a different path instead of `.` to analyze a project elsewhere on disk:

```bash
uvx skene-growth analyze /path/to/your/project
```

### Step 4: Generate a growth plan

```bash
uvx skene-growth plan
```

This reads `growth-manifest.json` and `growth-template.json` from `./skene-context/` (auto-detected) and generates a `growth-plan.md` file in the same directory.

The plan is produced by a "Council of Growth Engineers" analysis -- multiple specialized perspectives evaluate your codebase and converge on a prioritized growth strategy. The output includes:

- An executive summary
- Prioritized growth opportunities with implementation details
- A technical execution section with the recommended "next build"
- An implementation todo list

For activation-focused analysis instead of general growth, add the `--activation` flag:

```bash
uvx skene-growth plan --activation
```

### Step 5: Build an implementation prompt

```bash
uvx skene-growth build
```

This command:

1. Reads `growth-plan.md` from `./skene-context/` (auto-detected)
2. Extracts the Technical Execution section (the recommended next build, exact logic, data triggers, sequence)
3. Uses your LLM to generate a focused implementation prompt
4. Asks where you want to send it:
   - **Cursor** -- opens via deep link
   - **Claude** -- launches in terminal
   - **Show** -- prints the full prompt to the terminal

The prompt is also saved to a file in `./skene-context/` for later use.

> **Tip:** Use `--target` to skip the interactive menu. This is useful for scripting:
> ```bash
> uvx skene-growth build --target file   # Just save the prompt, no interaction
> ```

### Step 6: Check implementation status

After implementing the growth loop (using Cursor, Claude, or manually), verify that all requirements are met:

```bash
uvx skene-growth status
```

This loads the growth loop definitions from `./skene-context/growth-loops/` and uses AST parsing to verify that required files, functions, and patterns are present in your codebase. Each loop is marked **COMPLETE** or **INCOMPLETE** with details on what's missing.

For LLM-powered semantic matching to find alternative implementations:

```bash
uvx skene-growth status --find-alternatives --api-key "your-key"
```

## What you get

After running all six steps, your `./skene-context/` directory contains:

| File | Description |
|---|---|
| `growth-manifest.json` | Structured analysis of your codebase: tech stack, current growth features, opportunities |
| `growth-template.json` | Business-type-aware growth template with prioritized recommendations |
| `growth-plan.md` | Full growth plan with executive summary, priorities, and technical execution details |
| `implementation-prompt.md` | Ready-to-use prompt for your AI coding assistant |
| `growth-loops/*.json` | Growth loop definitions with file/function requirements for validation |

## Alternative: Quick one-liner

If you want to try the analysis without setting up a config file first, pass your API key inline:

```bash
uvx skene-growth analyze . --api-key "your-key"
```

This uses the default provider (openai) and model (gpt-4o). To use a different provider:

```bash
uvx skene-growth analyze . --api-key "your-key" --provider gemini --model gemini-3-flash-preview
```

## Alternative: Free preview (no API key)

If you want to see what skene-growth does before configuring an LLM, simply run `analyze` without an API key:

```bash
uvx skene-growth analyze .
```

When no API key is configured and you are not using a local provider, the command falls back to a sample growth analysis preview demonstrating the kind of strategic insights available with full API-powered analysis.

## Next steps

- [Analyze command in depth](../guides/analyze.md) -- all flags, output customization, excluding folders
- [Plan command in depth](../guides/plan.md) -- context directories, activation mode, custom manifest paths
- [Build command in depth](../guides/build.md) -- prompt generation, Cursor/Claude integration
- [Status command in depth](../guides/status.md) -- growth loop validation and alternative matching
- [Configuration reference](../guides/configuration.md) -- config files, environment variables, precedence rules
- [LLM providers](../guides/llm-providers.md) -- setup for OpenAI, Gemini, Anthropic, LM Studio, Ollama, and generic endpoints
