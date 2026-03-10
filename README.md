<p align="center">
  <img width="4000" height="800" alt="Skene_git" src="https://github.com/user-attachments/assets/2be11c04-6b98-4e26-8905-bf3250c4addb" />
  <a href="https://www.skene.ai"><img width="120" height="42" alt="website" src="https://github.com/user-attachments/assets/04e469ab-cd02-4526-bc5b-e5e0ca440fc6"></a>
  <a href="https://www.skene.ai/resources/docs/skene"><img width="103" height="42" alt="docs" src="https://github.com/user-attachments/assets/c63f96cb-52a9-4154-881b-37526b850f9b"></a>
  <a href="https://www.skene.ai/resources/blog"><img width="100" height="42" alt="blog" src="https://github.com/user-attachments/assets/baabe37b-0557-443e-9b01-6ae3951cf91b"></a>
  <a href="https://www.reddit.com/r/plgbuilders/"><img width="153" height="42" alt="reddit" src="https://github.com/user-attachments/assets/18d0df1b-81d9-4112-83f6-0a8fde5c189a"></a>
</p>

# Skene

[![PyPI version](https://img.shields.io/pypi/v/skene)](https://pypi.org/project/skene/)
[![Downloads](https://static.pepy.tech/badge/skene/month)](https://pepy.tech/projects/skene)
[![Commit Activity](https://img.shields.io/github/commit-activity/m/SkeneTechnologies/skene)](https://github.com/SkeneTechnologies/skene/commits)

PLG (Product-Led Growth) codebase analysis toolkit. Scan your codebase, detect growth opportunities, and generate actionable implementation plans.

## Quick Start

```bash
uvx skene config --init   # Create config file
uvx skene config          # Set provider, model, API key
uvx skene analyze .       # Analyze your codebase
uvx skene plan            # Generate a growth plan
uvx skene build           # Build an implementation prompt
uvx skene status          # Check loop implementation status
uvx skene push            # Deploy telemetry to Supabase + upstream
```

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
- **Telemetry deployment** -- generates Supabase migrations and pushes to upstream
- **Loop validation** -- verifies that growth loop requirements are implemented
- **Interactive chat** -- ask questions about your codebase in the terminal

Supports OpenAI, Gemini, Claude, LM Studio, Ollama, and any OpenAI-compatible endpoint. Free local audit available with no API key required.

<img width="1662" height="393" alt="ide_git" src="https://github.com/user-attachments/assets/0b9de3f8-9083-4dc8-b68e-105abc7ea0b4" />

## Installation

```bash
# Install uv (if you don't have it)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Recommended (no install needed)
uvx skene

# Or install globally
pip install skene
```

## Documentation

Full documentation: [www.skene.ai/resources/docs/skene](https://www.skene.ai/resources/docs/skene)

## Monorepo Structure

This repository contains two independent packages:

| Directory | Description | Language | Distribution |
|-----------|-------------|----------|-------------|
| `src/skene/` | CLI + analysis engine | Python | [PyPI](https://pypi.org/project/skene/) |
| `tui/` | Interactive terminal UI wizard | Go | [GitHub Releases](https://github.com/SkeneTechnologies/skene/releases) |

The TUI (`tui/`) is a Bubble Tea app that provides an interactive wizard experience and orchestrates the Python CLI via `uvx`. Each package has independent CI/CD pipelines.

## Contributing

Contributions are welcome. Please open an issue or submit a pull request on [GitHub](https://github.com/SkeneTechnologies/skene).

## License

[MIT](https://opensource.org/licenses/MIT)

<img width="4000" height="800" alt="Skene_end_git" src="https://github.com/user-attachments/assets/04119cd1-ee00-4902-9075-5fc3e1e5ec48" />

