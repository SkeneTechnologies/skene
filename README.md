<p align="center">
  <a href="https://www.skene.ai"><img src="https://img.shields.io/badge/Website-007ACC?style=flat&logo=google-chrome&logoColor=white" alt="Website"></a>
  <a href="https://www.skene.ai/resources/docs/skene"><img src="https://img.shields.io/badge/Docs-555?style=flat&logo=bookstack&logoColor=white" alt="Docs"></a>
  <a href="https://www.skene.ai/resources/blog"><img src="https://img.shields.io/badge/Blog-555?style=flat&logo=substack&logoColor=white" alt="Blog"></a>
  <a href="https://www.reddit.com/r/plgbuilders/"><img src="https://img.shields.io/badge/r%2Fplgbuilders-D84315?style=flat&logo=reddit&logoColor=white" alt="Reddit"></a>
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

## MCP Server

skene includes an MCP server for integration with AI assistants. Add to your assistant config:

```json
{
  "mcpServers": {
    "skene": {
      "command": "uvx",
      "args": ["--from", "skene[mcp]", "skene-mcp"],
      "env": {
        "SKENE_API_KEY": "your-api-key"
      }
    }
  }
}
```

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
