# Skene

A terminal interface for [Skene](https://github.com/SkeneTechnologies/skene). Guides you through selecting a repository, choosing an AI provider, and running growth analysis — all from the terminal.

Built with Go and [Bubble Tea](https://github.com/charmbracelet/bubbletea).

## What It Does

Skene terminal is the interactive front-end for **Skene** — a PLG analysis toolkit that models your product's user journey from your schema and code, surfaces growth opportunities along it, and turns them into actionable implementation plans.

The tool itself does **not** perform any analysis. It orchestrates `uvx skene` in your selected repository directory and displays the results.

## Features

- Step-by-step wizard — provider, model, authentication, project selection
- Multiple AI providers — OpenAI, Anthropic, Gemini or any OpenAI-compatible endpoint
- Authentication — Skene magic link, API key entry, local model auto-detection
- Existing analysis detection — detects previous `skene-context/` (or legacy `skene/`) output and offers to view or re-run
- Live terminal output during analysis
- Tabbed results view — User Journey, Growth Manifest, Growth Plan, Engine
- Next steps menu — generate plans, build prompts, validate, or re-analyse
- Cancellable processes — press `Esc` to cancel a running analysis
- Error handling with retry and go-back
- Cross-platform — macOS, Linux, Windows
- Mini-game while you wait

## Prerequisites

None. The CLI automatically downloads the [uv](https://docs.astral.sh/uv/) runtime on first use.

## Installation

### Quick Install (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash
```

This downloads the latest release binary for your platform and installs it to `/usr/local/bin`.

To install a specific version:

```bash
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | VERSION=tui-v0.4.0 bash
```

### Clone and Run

```bash
git clone https://github.com/SkeneTechnologies/skene.git
cd skene/tui
make build
make run
```

### Build from Source (requires Go 1.22+)

```bash
git clone https://github.com/SkeneTechnologies/skene.git
cd skene/tui
make install   # download dependencies
make build
make run
```

### Install to PATH

```bash
make install-bin   # copies build/skene to /usr/local/bin
```

## Usage

Run `skene` and follow the steps:

```
Welcome
  → AI Provider (OpenAI, Anthropic, Gemini, Generic)
    → Model selection
      → Authentication (magic link / API key / local model)
        → Project directory
          → Analysis configuration
            → Running analysis
              → Results dashboard
                → Next steps
```

### Keyboard Controls

| Key | Action |
|-----|--------|
| `↑/↓` or `j/k` | Navigate |
| `←/→` or `h/l` | Navigate / switch tabs |
| `Enter` | Confirm |
| `Esc` | Go back / cancel |
| `Tab` | Switch focus |
| `Space` | Toggle option |
| `?` | Help overlay |
| `g` | Mini-game (during analysis) |
| `Ctrl+C` | Quit |

## Configuration

Config files are checked in order (first found wins):

1. **Project** — `.skene.config` in the project directory
2. **User** — `~/.config/skene/config`

Example `.skene.config`:

```json
{
  "provider": "gemini",
  "model": "gemini-3-flash-preview",
  "api_key": "your-api-key",
  "output_dir": "./skene-context",
  "verbose": true,
  "use_growth": true
}
```

### Supported Providers

| Provider | ID | Auth |
|----------|----|------|
| Skene | `skene` | Magic link (free tokens) |
| OpenAI | `openai` | API key |
| Anthropic | `anthropic` | API key |
| Gemini | `gemini` | API key |
| Generic | `generic` | API key + base URL |

## Development

```bash
make dev          # live reload (requires air)
make test         # run tests
make lint         # lint
make fmt          # format
make build-all    # build for all platforms
make release      # package releases
```

## Dependencies

- [Bubble Tea](https://github.com/charmbracelet/bubbletea) — TUI framework
- [Lip Gloss](https://github.com/charmbracelet/lipgloss) — Styling
- [Bubbles](https://github.com/charmbracelet/bubbles) — UI components
- [pkg/browser](https://github.com/pkg/browser) — Browser opening for auth

## Related

- [skene](https://github.com/SkeneTechnologies/skene) — PLG analysis toolkit (Python CLI)

## License

MIT
