# Login Command

The `login` and `logout` commands manage authentication with Skene Cloud upstream, which is required for pushing growth loops and telemetry via the `push` command.

## Prerequisites

- A Skene Cloud workspace URL (e.g. `https://skene.ai/workspace/my-app`)
- An API token for your workspace. Get your workspace api-key here: https://www.skene.ai/workspace/apikeys

## Basic usage

Log in to upstream:

```bash
uvx skene login --upstream https://skene.ai/workspace/my-app
```

The command prompts you for a token, validates it against the upstream API, and saves the credentials.

Check login status:

```bash
uvx skene login --status
```

Log out:

```bash
uvx skene logout
```

## Flag reference

### `login`

| Flag | Short | Description |
|------|-------|-------------|
| `--upstream TEXT` | `-u` | Upstream workspace URL |
| `--status` | `-s` | Show current login status for this project |

### `logout`

No options. Removes saved credentials for the current project.

## How credentials are stored

Login saves upstream URL, workspace slug, and API key to `.skene.config` in the project directory (restrictive permissions `0600`). This file is gitignored by default.

Logout removes those fields from the same file, preserving other settings.

## Token resolution

When commands need an upstream token, it is resolved in this order:

1. `SKENE_UPSTREAM_API_KEY` environment variable
2. `upstream_api_key` field in `.skene.config`

## Next steps

- [Push](push.md) -- Push growth loops and telemetry to upstream
- [Configuration](configuration.md) -- Config files, env vars, and priority
