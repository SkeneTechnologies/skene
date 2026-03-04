<p align="center">
  <a href="https://www.skene.ai"><img src="https://img.shields.io/badge/Website-007ACC?style=flat&logo=google-chrome&logoColor=white" alt="Website"></a>
  <a href="https://www.skene.ai/resources/docs/skene-growth"><img src="https://img.shields.io/badge/Docs-555?style=flat&logo=bookstack&logoColor=white" alt="Docs"></a>
  <a href="https://www.skene.ai/resources/blog"><img src="https://img.shields.io/badge/Blog-555?style=flat&logo=substack&logoColor=white" alt="Blog"></a>
  <a href="https://www.reddit.com/r/plgbuilders/"><img src="https://img.shields.io/badge/r%2Fplgbuilders-D84315?style=flat&logo=reddit&logoColor=white" alt="Reddit"></a>
</p>

# skene-growth

[![PyPI version](https://img.shields.io/pypi/v/skene-growth)](https://pypi.org/project/skene-growth/)
[![Downloads](https://static.pepy.tech/badge/skene-growth/month)](https://pepy.tech/projects/skene-growth)
[![Commit Activity](https://img.shields.io/github/commit-activity/m/SkeneTechnologies/skene-growth)](https://github.com/SkeneTechnologies/skene-growth/commits)

PLG (Product-Led Growth) codebase analysis toolkit. Scan your codebase, detect growth opportunities, and generate actionable implementation plans.

## Quick Start

```bash
uvx skene-growth config --init   # Create config file
uvx skene-growth config          # Set provider, model, API key
uvx skene-growth analyze .       # Analyze your codebase
uvx skene-growth plan            # Generate a growth plan
uvx skene-growth build           # Build an implementation prompt
uvx skene-growth status          # Check loop implementation status
```

## What It Does

- **Tech stack detection** -- identifies frameworks, databases, auth, deployment
- **Growth feature discovery** -- finds existing signup flows, sharing, invites, billing
- **Revenue leakage analysis** -- spots missing monetization and weak pricing tiers
- **Growth plan generation** -- produces prioritized growth loops with implementation roadmaps
- **Implementation prompts** -- builds ready-to-use prompts for Cursor, Claude, or other AI tools
- **Loop validation** -- AST-based checks verify that growth loop requirements are implemented
- **Interactive chat** -- ask questions about your codebase in the terminal

Supports OpenAI, Gemini, Claude, LM Studio, Ollama, and any OpenAI-compatible endpoint. Free local audit available with no API key required.

## Installation

```bash
# Install uv (if you don't have it)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Recommended (no install needed)
uvx skene-growth

# Or install globally
pip install skene-growth
```

## Documentation

Full documentation: [www.skene.ai/resources/docs/skene-growth](https://www.skene.ai/resources/docs/skene-growth)

## MCP Server

skene-growth includes an MCP server for integration with AI assistants. Add to your assistant config:

```json
{
  "mcpServers": {
    "skene-growth": {
      "command": "uvx",
      "args": ["--from", "skene-growth[mcp]", "skene-growth-mcp"],
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
| `src/skene_growth/` | CLI + analysis engine | Python | [PyPI](https://pypi.org/project/skene-growth/) |
| `tui/` | Interactive terminal UI wizard | Go | [GitHub Releases](https://github.com/SkeneTechnologies/skene-growth/releases) |

The TUI (`tui/`) is a Bubble Tea app that provides an interactive wizard experience and orchestrates the Python CLI via `uvx`. Each package has independent CI/CD pipelines.

## Contributing

Contributions are welcome. Please open an issue or submit a pull request on [GitHub](https://github.com/SkeneTechnologies/skene-growth).

## License

[MIT](https://opensource.org/licenses/MIT)
