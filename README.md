<p align="center">
  <img alt="Skene_git" src="https://github.com/user-attachments/assets/2be11c04-6b98-4e26-8905-bf3250c4addb" width="100%" height="auto" />
</p>



<p align="center">
  <a href="https://www.skene.ai"><img width="120" height="42" alt="website" src="https://github.com/user-attachments/assets/8ae8c68f-eeb5-411f-832f-6b6818bd2c34"></a>&nbsp;<a href="https://www.skene.ai/resources/docs/skene"><img width="120" height="42" alt="docs" src="https://github.com/user-attachments/assets/f847af52-0f6f-4570-9a48-1b7c8f4f0d7a"></a>&nbsp;<a href="https://www.skene.ai/resources/blog"><img width="100" height="42" alt="blog" src="https://github.com/user-attachments/assets/8c62e3b8-39a8-43f6-bb0b-f00b118aff82"></a>&nbsp;<a href="https://www.reddit.com/r/plgbuilders/"><img width="153" height="42" alt="reddit" src="https://github.com/user-attachments/assets/b420ea50-26e3-40fe-ab34-ac179f748357"></a>
</p>


Skene is a codebase analysis toolkit for product-led growth. It scan your codebase, detect growth opportunities, and generate actionable implementation plans.

## Quick Start

Install and launch the interactive terminal UI:

```bash
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash
skene
```

The wizard walks you through provider selection, authentication, and analysis — no configuration needed upfront.

<p align="center">
  <img src="https://github.com/user-attachments/assets/49dcd0c4-2bad-4fd3-b29e-89ba2b85c669" width="100%" height="auto"/>
<p>

## What It Does

- **Tech stack detection** -- identifies frameworks, databases, auth, deployment
- **Growth feature discovery** -- finds existing signup flows, sharing, invites, billing
- **Feature registry** -- tracks features across analysis runs, links them to growth loops
- **Revenue leakage analysis** -- spots missing monetization and weak pricing tiers
- **Growth plan generation** -- produces prioritized growth loops with implementation roadmaps
- **Implementation prompts** -- builds ready-to-use prompts for Cursor, Claude, or other AI tools
- **Telemetry deployment** -- `build` writes `supabase/migrations/*_skene_triggers.sql`; `push` sends engine + that SQL to upstream
- **Loop validation** -- verifies that growth loop requirements are implemented
- **Interactive chat** -- ask questions about your codebase in the terminal

Supports OpenAI, Gemini, Claude, LM Studio, Ollama, and any OpenAI-compatible endpoint. Free local audit available with no API key required.

<img width="1662" height="393" alt="ide_git" src="https://github.com/user-attachments/assets/0b9de3f8-9083-4dc8-b68e-105abc7ea0b4" />

## Installation

### Terminal UI (recommended)

The TUI is an interactive wizard that guides you through the entire workflow. No prerequisites — the installer handles everything.

```bash
# Install the TUI
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash

# Launch it
skene
```

### Python CLI

If you prefer the command line, you can run Skene directly with `uvx` (no install needed) or install it globally:

```bash
# Install uv (if you don't have it)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Run directly (no install needed)
uvx skene

# Or install globally
pip install skene
```

For CLI usage details, see the [documentation](https://www.skene.ai/resources/docs/skene).

## Output Layout

Both the Python CLI (including `analyse-journey`, `analyze`, `plan`, and `build`) and the interactive TUI write their artifacts to a single bundle directory in your project root. The directory is created automatically when it is missing.

- **Default:** `./skene/` — holds `schema.yaml`, `engine.yaml`, `growth-manifest.json`, `growth-template.json`, `growth-plan.md`, `feature-registry.json`, and related assets.
- **Legacy:** `./skene-context/` — the previous default. Existing projects continue to work: discovery commands (`plan`, `build`, `push`, `features export`, TUI detection) look for `./skene/` first and fall back to `./skene-context/` when only the legacy directory is present.
- **Override:** set `output_dir` in `.skene.config` or pass `-o`/`--output` to a specific command to write elsewhere.

## Monorepo Structure

| Directory | Description | Language | Distribution |
|-----------|-------------|----------|-------------|
| `src/skene/` | CLI + analysis engine | Python | [PyPI](https://pypi.org/project/skene/) |
| `tui/` | Interactive terminal UI wizard | Go | [GitHub Releases](https://github.com/SkeneTechnologies/skene/releases) |
| `cursor-plugin/` | Cursor IDE plugin | — | — |
| `skills/` | Skene Skills -- composable backend schemas for Supabase | SQL | [npm](https://www.npmjs.com/package/@skene/database-skills) |

The TUI (`tui/`) is a Bubble Tea app that provides an interactive wizard experience and orchestrates the Python CLI via `uvx`. Each package has independent CI/CD pipelines.

## Contributing

Contributions are welcome. Please [open an issue](https://github.com/SkeneTechnologies/skene/issues) or submit a [pull request](https://github.com/SkeneTechnologies/skene/pulls).

## License

[MIT](https://opensource.org/licenses/MIT)

<img alt="Skene_end_git" src="https://github.com/user-attachments/assets/04119cd1-ee00-4902-9075-5fc3e1e5ec48" width="100%" height="auto" />
