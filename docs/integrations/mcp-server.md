# MCP Server

skene provides an [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that exposes codebase analysis capabilities to AI assistants like Claude Desktop and Claude Code.

The server communicates via stdio and exposes 12 tools organized into tiers by speed and complexity. Tier 1 tools run in under a second with no LLM calls. Tier 2 tools perform LLM-powered analysis with automatic caching. Tier 3 tools combine cached results into final outputs.

## Installation

Install with the `mcp` optional dependency:

```bash
# With pip
pip install skene[mcp]

# With uv
uv pip install skene[mcp]
```

Or run directly with `uvx` (no installation required):

```bash
uvx --from "skene[mcp]" skene-mcp
```

## Configuration

### Claude Desktop

Add to your Claude Desktop config file:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

**Option 1: Installed locally**

```json
{
  "mcpServers": {
    "skene": {
      "command": "skene-mcp",
      "env": {
        "SKENE_API_KEY": "your-api-key"
      }
    }
  }
}
```

**Option 2: Via uvx (no install needed)**

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

### Claude Code

Add to `.mcp.json` in your project root or `~/.claude/settings.json` for global configuration:

```json
{
  "mcpServers": {
    "skene": {
      "command": "skene-mcp",
      "env": {
        "SKENE_API_KEY": "your-api-key"
      }
    }
  }
}
```

The `uvx` variant works identically -- use `"command": "uvx"` with `"args": ["--from", "skene[mcp]", "skene-mcp"]`.

## Available Tools

### Tier 1: Quick Tools (< 1s, no LLM)

These tools run instantly and require no LLM provider configuration.

| Tool | Input | Output | Description |
|------|-------|--------|-------------|
| `get_codebase_overview` | `path` | `tree`, `file_counts`, `total_files`, `config_files` | Directory tree, file counts by extension, detected config files |
| `search_codebase` | `path`, `pattern`, `directory` (default `"."`) | `matches`, `count` | Search files by glob pattern (e.g., `**/*.py`, `src/**/*.ts`) |

### Tier 2: Analysis Tools (5-15s, uses LLM, cached)

These tools call the configured LLM provider and cache results per phase. Each tool accepts `path` (required) and `force_refresh` (optional boolean, default `false`).

| Tool | Output Key | Description |
|------|------------|-------------|
| `analyze_tech_stack` | `tech_stack`, `cached` | Framework, language, database, auth, deployment detection |
| `analyze_product_overview` | `product_overview`, `cached` | Product name, tagline, description, value proposition from README/docs |
| `analyze_growth_hubs` | `current_growth_features`, `cached` | Viral/growth features: invitations, sharing, referrals, payments |
| `analyze_features` | `features`, `cached` | User-facing features extracted from source files |
| `analyze_industry` | `industry`, `cached` | Industry classification, sub-verticals, business model tags |

### Tier 3: Generation Tools (5-15s)

These tools combine cached analysis results into final outputs.

| Tool | Input | Output | Description |
|------|-------|--------|-------------|
| `generate_manifest` | `path`, `product_docs`, `force_refresh` | `manifest`, `cached` | Combine analysis phases into a GrowthManifest. **Call `analyze_tech_stack` and `analyze_growth_hubs` first.** For `product_docs=true`, also call `analyze_product_overview` and `analyze_features` first. |
| `generate_growth_template` | `path`, `business_type`, `force_refresh` | `template`, `cached` | Create PLG template with lifecycle stages, milestones, and metrics from a manifest |
| `write_analysis_outputs` | `path`, `product_docs` | `output_dir`, `written_files` | Write `growth-manifest.json`, optionally `product-docs.md` and `growth-template.json` to `./skene-context/` |

### Utility Tools

| Tool | Input | Output | Description |
|------|-------|--------|-------------|
| `get_manifest` | `path` | `manifest` or `None`, `exists`, `manifest_path` | Read an existing manifest from disk without re-analyzing |
| `clear_cache` | `path` (optional) | `cleared`, `message` | Clear cached analysis results. Omit `path` to clear all entries. |

## Typical Workflow

The tools are designed to be called in a specific sequence. Tier 2 analysis tools populate a cache, and Tier 3 generation tools read from that cache.

```
1. get_codebase_overview        -- Understand project structure
2. analyze_tech_stack           -- Detect technologies (cached)
3. analyze_growth_hubs          -- Find growth features (cached)
4. generate_manifest            -- Combine into GrowthManifest (reads cache)
5. generate_growth_template     -- Create PLG template (optional)
6. write_analysis_outputs       -- Save files to ./skene-context/
```

For a full analysis with product documentation, add `analyze_product_overview` and `analyze_features` before `generate_manifest`, and pass `product_docs=true` to both `generate_manifest` and `write_analysis_outputs`.

## Cache Configuration

The MCP server caches Tier 2 analysis results to avoid redundant LLM calls. The cache uses a two-layer strategy:

- **Memory cache**: In-process dictionary, fastest lookup
- **Disk cache**: JSON files in the cache directory, persists across server restarts

### Invalidation

Cache entries are automatically invalidated when:

- The TTL expires (default: 1 hour)
- **Marker file hashes change** -- any modification to dependency/config files triggers invalidation. Tracked files include: `package.json`, `requirements.txt`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `Gemfile`, `composer.json`, and their lockfiles.
- **Source directory mtimes change** -- modifications to common source directories (`src`, `lib`, `app`, `pages`, `components`, `api`, `server`, `client`) trigger invalidation.

You can also manually invalidate with the `clear_cache` tool or by passing `force_refresh=true` to any analysis tool.

### Phase-Specific Keys

Each analysis phase has its own independent cache entry. Running `analyze_tech_stack` does not invalidate the cache for `analyze_growth_hubs`. The phases are: `tech_stack`, `product_overview`, `current_growth_features`, `features`, `industry`, `manifest`, `growth_template`.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SKENE_API_KEY` | API key for the LLM provider | (required for cloud providers) |
| `SKENE_PROVIDER` | LLM provider: `openai`, `gemini`, `anthropic`, `lmstudio`, `ollama`, `generic` | `openai` |
| `SKENE_MODEL` | Model name to use | Provider default |
| `SKENE_CACHE_ENABLED` | Enable or disable caching (`true`/`false`) | `true` |
| `SKENE_CACHE_DIR` | Directory for disk cache | `~/.cache/skene-mcp` |
| `SKENE_CACHE_TTL` | Cache time-to-live in seconds | `3600` |

## Using Local LLMs

For LM Studio or Ollama, no API key is needed. Set `SKENE_PROVIDER` in the `env` block:

```json
{
  "mcpServers": {
    "skene": {
      "command": "skene-mcp",
      "env": {
        "SKENE_PROVIDER": "lmstudio",
        "SKENE_MODEL": "your-loaded-model"
      }
    }
  }
}
```

For Ollama, use `"SKENE_PROVIDER": "ollama"`. The server connects to the default local endpoint for each provider.

See [LLM Providers](../guides/llm-providers.md) for details on configuring each provider.

## Running Manually

You can start the MCP server directly for testing or debugging:

```bash
# Via the entry point
skene-mcp

# Via Python module
python -m skene.mcp
```

The server communicates via stdio (standard input/output) as required by the MCP protocol. It is not meant to be run interactively -- it expects JSON-RPC messages on stdin and writes responses to stdout.

## Next Steps

- [Configuration](../guides/configuration.md) -- config file options and environment variable priority
- [LLM Providers](../guides/llm-providers.md) -- setup for OpenAI, Gemini, Claude, LM Studio, Ollama
- [CLI Reference](../reference/cli.md) -- the full CLI if you prefer command-line usage over MCP
