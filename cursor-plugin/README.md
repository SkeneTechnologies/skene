# Skene PLG Analyzer — Cursor Plugin

Product-Led Growth codebase analysis toolkit for [Cursor IDE](https://cursor.com).

Map the customer journey encoded in your code and database schema — all without leaving your editor.

## Features

| Capability | Description |
|-----------|-------------|
| **Journey Analysis** | `skene analyse-journey` maps your product's user lifecycle into a `journey.yaml` |
| **Telemetry Deployment** | `skene push` uploads `engine.yaml` + trigger migrations to upstream |
| **Validation** | Verify that engine features are actually implemented (`skene status`) |
| **Best Practices** | Always-on PLG guidance via Cursor rules |

## Quick Start

### 1. Install locally (development)

```bash
bash cursor-plugin/scripts/install-local.sh
```

Then restart Cursor.

### 2. Run your first command

Open a project and type `/skene-init` in the Cursor agent to configure Skene.

## Commands

| Command | Description |
|---------|-------------|
| `/skene-init` | Initialize Skene configuration |
| `/skene-status` | Check implementation progress |
| `/skene-deploy` | Push engine + trigger migration to upstream |

## Skills

Skills are invoked automatically by the Cursor agent based on context, or triggered via commands:

- **initialize-config** — First-time Skene setup
- **deploy-telemetry** — Analytics infrastructure setup
- **validate-loop** — Implementation verification

## Requirements

- [Cursor IDE](https://cursor.com) 2.5+
- Python 3.10+
- `uvx` (install via `pip install uv`)
- Skene CLI (`uvx skene` — installed automatically via uvx)
- Optional: Supabase project (for telemetry deployment)

## Configuration

Skene uses a **TOML config file** `.skene.config` in your project root. Run `/skene-init` to set it up, or configure manually:

```bash
uvx skene config --init    # create .skene.config
uvx skene config          # interactive: provider, model, API key (or set SKENE_API_KEY)
```

Config options and env vars: [Configuration guide](https://www.skene.ai/resources/docs/skene/guides/configuration).

### Supported LLM providers

- OpenAI (GPT-4o, GPT-4-turbo)
- Anthropic (Claude 3.5 Sonnet, Claude 4)
- Google (Gemini 2.5 Pro)
- LM Studio (local, no API key)
- Ollama (local, no API key)

## Plugin Structure

```
cursor-plugin/
├── .cursor-plugin/
│   └── plugin.json         # Plugin manifest
├── skills/                  # Agent skills (3 skills)
│   ├── initialize-config/
│   ├── deploy-telemetry/
│   └── validate-loop/
├── commands/                # Slash commands (3 commands)
├── hooks/
│   └── hooks.json           # Automation hooks
├── rules/
│   └── skene-best-practices.mdc
├── scripts/                 # Install and hook scripts
├── assets/
│   └── logo.svg
├── README.md
├── CHANGELOG.md
└── LICENSE
```

## Development

### Local install

```bash
bash cursor-plugin/scripts/install-local.sh
```

This copies the plugin to `~/.cursor/plugins/` and registers it with Cursor's plugin system.

### Uninstall

```bash
bash cursor-plugin/scripts/uninstall-local.sh
```

### Dev loop

1. Edit plugin files in `cursor-plugin/`
2. Run `bash cursor-plugin/scripts/install-local.sh`
3. Restart Cursor (Cmd+Shift+P → "Reload Window" or full restart)
4. Test your changes
5. Repeat

## Resources

- [Skene Documentation](https://www.skene.ai/resources/docs/skene)
- [Cursor Plugin Docs](https://cursor.com/docs/reference/plugins)

## License

MIT — see [LICENSE](LICENSE).
