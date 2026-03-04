# skene-growth

PLG (Product-Led Growth) analysis toolkit for codebases. Analyze your code, detect growth opportunities, and generate documentation of your stack.

## Quick Start

**No installation required** - just run with [uvx](https://docs.astral.sh/uv/):

```bash
#install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Analyze your codebase
uvx skene-growth analyze . --api-key "your-openai-api-key"

# Or set the API key as environment variable
export SKENE_API_KEY="your-openai-api-key"
uvx skene-growth analyze .
```

Get an OpenAI API key at: https://platform.openai.com/api-keys

## What It Does

skene-growth scans your codebase and generates a **growth manifest** containing:

- **Tech Stack Detection** - Framework, language, database, auth, deployment
- **Current Growth Features** - Existing features with growth potential (signup flows, sharing, invites, billing)
- **Revenue Leakage** - Potential revenue issues (missing monetization, weak pricing tiers, overly generous free tiers)
- **Growth Opportunities** - Missing features that could drive user acquisition and retention

With the `--product-docs` flag, it also collects:

- **Product Overview** - Tagline, value proposition, target audience
- **Features** - User-facing feature documentation with descriptions and examples
- **Product Docs** - Generates user-friendly product-docs.md file

After the manifest is created, skene-growth generates a **custom growth template** (JSON)
using LLM analysis. The templates use examples in `src/templates/` as 
reference but create custom lifecycle stages and keywords specific to your product.

## Installation

### Option 1: uvx (Recommended)

Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Zero installation - runs instantly (requires API key):

```bash
uvx skene-growth analyze . --api-key "your-openai-api-key"
uvx skene-growth validate ./growth-manifest.json
```

> **Note:** The `analyze` command requires an API key. By default, it uses OpenAI (get a key at https://platform.openai.com/api-keys). You can also use Gemini with `--provider gemini`, Anthropic with `--provider anthropic` or `--provider claude`, local LLMs with `--provider lmstudio` or `--provider ollama` (experimental), or any OpenAI-compatible endpoint with `--provider generic --base-url "https://your-api.com/v1"`.

### Option 2: pip install

```bash
pip install skene-growth
```

## How to use?

skene-growth follows a flexible workflow:

1. **analyze** - Analyze your codebase and generate a growth manifest (tech stack, growth features, opportunities, growth template).
2. **plan** - Generate a growth plan using Council of Growth Engineers (3-5 high-impact loops, roadmap, recommendations).
3. **build** - Extract Technical Execution from the plan, generate an implementation prompt, save growth loop definition, and send to Cursor/Claude.
4. **status** - Verify implementation status of growth loop requirements (files, functions) against your codebase.

## CLI Commands

### `analyze` - Analyze a codebase

Requires an API key (set via `--api-key`, `SKENE_API_KEY` env var, or config file).

```bash
# Analyze current directory (uses OpenAI by default)
uvx skene-growth analyze . --api-key "your-openai-api-key"

# Using environment variable
export SKENE_API_KEY="your-openai-api-key"
uvx skene-growth analyze .

# Analyze specific path with custom output
uvx skene-growth analyze ./my-project -o manifest.json

# With verbose output
uvx skene-growth analyze . -v

# Use a specific model
uvx skene-growth analyze . --model gpt-4o

# Use Gemini instead of OpenAI (v1beta API uses -preview suffix)
uvx skene-growth analyze . --provider gemini --model gemini-3-flash-preview --api-key "your-gemini-api-key"

# Use Anthropic (Claude) - both "anthropic" and "claude" work
uvx skene-growth analyze . --provider anthropic --api-key "your-anthropic-api-key"
uvx skene-growth analyze . --provider claude --api-key "your-anthropic-api-key"

# Use LM Studio (local server)
uvx skene-growth analyze . --provider lmstudio --model "your-loaded-model"

# Use Ollama (local server) - Experimental
uvx skene-growth analyze . --provider ollama --model "llama3.3"

# Use any OpenAI-compatible endpoint (generic provider)
uvx skene-growth analyze . --provider generic --base-url "https://your-api.com/v1" --api-key "your-key" --model "your-model"

# Generic provider with local endpoint (no API key required)
uvx skene-growth analyze . --provider generic --base-url "http://localhost:8000/v1" --model "local-model"

# Generate product documentation (collects product overview and features)
uvx skene-growth analyze . --product-docs

# Exclude folders from analysis (can be used multiple times)
uvx skene-growth analyze . --exclude tests --exclude vendor --exclude migrations
uvx skene-growth analyze . -e planner -e docs
```

**Output:**
- `./skene-context/growth-manifest.json` (structured data)
- `./skene-context/growth-template.json` (custom template with lifecycle stages and keywords)
- `./skene-context/product-docs.md` (if --product-docs flag used)

**Growth Templates:** The system generates custom templates with lifecycle stages and keywords specific to your user journey, inferred from your codebase.

**Flags:**
- `--product-docs`: Generate user-friendly product documentation (collects product overview, features, and generates product-docs.md)
- `-e, --exclude`: Folder names to exclude from analysis (can be used multiple times). Can also be configured in `.skene-growth.config`.
- `--debug`: Log all LLM input/output to `.skene-growth/debug/`

### `validate` - Validate a manifest

```bash
uvx skene-growth validate ./growth-manifest.json
```

### `plan` - Generate growth plan

Generate a growth plan using Council of Growth Engineers analysis. This command uses an LLM to analyze your manifest and template to produce actionable growth recommendations.

**Prerequisites:**
- `growth-manifest.json` file (generated by the `analyze` command)
- `growth-template.json` file (generated by the `analyze` command)
- API key for LLM provider

```bash
# Generate growth plan (auto-detects manifest and template)
uvx skene-growth plan --api-key "your-key"

# Specify context directory containing manifest and template
uvx skene-growth plan --context ./my-context --api-key "your-key"

# Specify all files explicitly
uvx skene-growth plan --manifest ./manifest.json --template ./template.json

# Use different provider/model
uvx skene-growth plan --provider gemini --model gemini-3-flash-preview

# Add user context to influence generation
uvx skene-growth plan --prompt "Focus on enterprise customers" --api-key "your-key"
```

**Output:**
- `./skene-context/growth-plan.md` (default) or custom path specified with `-o`

**Flags:**
- `--manifest`: Path to growth-manifest.json (auto-detected if not specified)
- `--template`: Path to growth-template.json (auto-detected if not specified)
- `-c, --context`: Directory containing growth-manifest.json and growth-template.json (auto-detected if not specified)
- `-o, --output`: Output path for growth plan (markdown format)
- `--api-key`: API key for LLM provider (or set SKENE_API_KEY env var)
- `-p, --provider`: LLM provider (openai, gemini, anthropic/claude, lmstudio, ollama, generic)
- `-m, --model`: LLM model name
- `--prompt`: Additional user prompt to influence plan generation
- `--debug`: Log all LLM input/output to `.skene-growth/debug/`

**Council of Growth Engineers Analysis:**
The plan command uses a "Council of Growth Engineers" system prompt that acts as an elite advisory board of growth strategists. It provides:
- Assessment of current state and opportunities
- 3-5 selected high-impact growth loops with detailed implementation steps
- Week-by-week implementation roadmap
- Key callouts on what to avoid and what to prioritize
- Specific metrics and measurement strategies

### `build` - Build growth loop implementation

Generate an intelligent prompt from your growth plan and optionally save the loop definition for verification.

**Prerequisites:**
- `growth-plan.md` file (generated by the `plan` command)
- API key for LLM provider (configured in `.skene-growth.config`)

```bash
# Build from growth plan (uses config for LLM)
uvx skene-growth build

# Override LLM settings
uvx skene-growth build --api-key "your-key" --provider gemini

# Specify custom plan location
uvx skene-growth build --plan ./my-plan.md

# Use custom context directory
uvx skene-growth build --context ./my-context

# Enable debug logging
uvx skene-growth build --debug
```

**What it does:**
1. Extracts Technical Execution section from growth plan
2. Uses LLM to generate an intelligent, focused implementation prompt
3. **Saves growth loop definition** to `<output_dir>/growth-loops/<loop_name>_<timestamp>.json`
   - Conforms to GROWTH_LOOP_VERIFICATION_SPEC schema
   - Includes file/function/integration/telemetry requirements
   - Preserves history with timestamped files
4. Prompts where to send the implementation prompt (Cursor/Claude/Show)

**Output:**
- Growth loop JSON saved to `./skene-context/growth-loops/` (or custom `output_dir`)
- Interactive prompt for implementation destination

**Growth Loop Storage:**
- Growth loop definitions are automatically saved as JSON files when using the `build` command
- Files are stored in `./skene-context/growth-loops/` directory (or custom `output_dir` if specified)
- Filename format: `YYYYMMDD_HHMMSS_<loop_id>.json` (e.g., `20240204_143022_share_flag.json`)

- Existing growth loops are automatically loaded and referenced in subsequent analyses to avoid duplicates

### `status` - Show implementation status of growth loops

Verifies that required files, functions, and patterns from growth loop definitions are implemented in your codebase.

```bash
uvx skene-growth status
uvx skene-growth status ./my-project --context ./my-project/skene-context
uvx skene-growth status --find-alternatives --api-key "your-key"
```

**Flags:**
- `-c, --context`: Path to skene-context directory (auto-detected if omitted)
- `--find-alternatives`: Use LLM to find existing functions that might fulfill missing requirements (requires API key)

### `config` - Manage configuration

```bash
# Show current configuration (default)
uvx skene-growth config --show

# Create a sample config file in current directory
uvx skene-growth config --init
```

## Excluding Folders from Analysis

You can exclude specific folders from analysis to skip test files, vendor directories, documentation, or any other folders you don't want analyzed.

### How Exclusion Works

Excluding `"test"` matches paths containing that string: `tests`, `test_utils`, `integration_tests`, `src/tests/unit/file.py`. Path patterns like `"tests/unit"` match any path containing that substring.

### Examples

```bash
# Exclude test folders and vendor directories
uvx skene-growth analyze . --exclude tests --exclude vendor

# Exclude multiple folders (short form)
uvx skene-growth analyze . -e planner -e migrations -e docs

# Exclude path patterns (matches paths containing the string)
uvx skene-growth analyze . --exclude "tests/unit" --exclude "vendor"
```

### Default Exclusions

Common build and cache directories are excluded by default: `.git`, `__pycache__`, `node_modules`, `.idea`, `.vscode`, `venv`, `.venv`, `dist`, `build`, `.next`, `.nuxt`, `coverage`, `.cache`. Your custom exclusions are merged with these.

## Configuration

skene-growth supports configuration files for storing defaults:

### Configuration Files

| Location | Purpose |
|----------|---------|
| `./.skene-growth.config` | Project-level config (checked into repo) |
| `~/.config/skene-growth/config` | User-level config (personal settings) |

### Sample Config File

```toml
# .skene-growth.config

# API key for LLM provider (can also use SKENE_API_KEY env var)
# api_key = "your-api-key"

# LLM provider to use: "openai" (default), "gemini", "anthropic"/"claude", "lmstudio", "ollama" (experimental), or "generic"
provider = "openai"

# Model to use (provider-specific defaults apply if not set)
# openai: gpt-4o | gemini: gemini-3-flash-preview | anthropic: claude-sonnet-4-5 | ollama: llama3.3
# model = "gpt-4o"

# Base URL for OpenAI-compatible endpoints (required for "generic" provider)
# Can also be set via SKENE_BASE_URL env var or --base-url CLI flag
# base_url = "https://your-api.com/v1"

# Default output directory
output_dir = "./skene-context"

# Enable verbose output
verbose = false

# Log LLM input/output to .skene-growth/debug/ (or set SKENE_DEBUG=1)
# debug = false

# Folders to exclude from analysis (folder names or path patterns)
# Excludes any folder containing these names anywhere in the path
# Examples: "test" will exclude "tests", "test_utils", "integration_tests"
# Path patterns like "tests/unit" will exclude any path containing that pattern
exclude_folders = ["tests", "vendor", "migrations", "docs"]
```

### Configuration Priority

Settings are loaded in this order (later overrides earlier):

1. User config (`~/.config/skene-growth/config`)
2. Project config (`./.skene-growth.config`)
3. Environment variables (`SKENE_API_KEY`, `SKENE_PROVIDER`)
4. CLI arguments

## Upstream

Push deploy artifacts (migrations, edge functions, growth loops) to a remote workspace.

### Login

Each project folder stores its own upstream connection. Run `skene login` from the project root:

```bash
skene login --upstream https://skene.ai/workspace/my-app
```

This creates two things:

| File | Location | Contents |
|------|----------|----------|
| `.skene-upstream` | Project directory | Upstream URL, workspace slug, timestamp (no secrets) |
| `credentials` | `~/.config/skene-growth/credentials` | Tokens keyed by workspace slug (0o600 permissions) |

Different projects can target different workspaces without overwriting each other.

### Token Resolution

When running `skene deploy`, the token is resolved in this order:

1. **Workspace-keyed token** from `~/.config/skene-growth/credentials` (matched by the workspace slug in `.skene-upstream`)
2. **`SKENE_UPSTREAM_TOKEN`** environment variable
3. **`upstream_token`** in `.skene-growth.config`
4. Legacy global `token` from credentials file

### Deploy

```bash
# Uses upstream + token from .skene-upstream / credentials
skene deploy

# Override upstream for this run
skene deploy --upstream https://skene.ai/workspace/other-app

# Re-push without regenerating
skene deploy --push-only
```

### Status & Logout

```bash
# Check current login state for this project
skene login --status

# Remove project upstream and workspace token
skene logout
```

## Python API

### CodebaseExplorer

Safe, sandboxed access to codebase files:

```python
from skene_growth import CodebaseExplorer

# Create explorer with default exclusions
explorer = CodebaseExplorer("/path/to/repo")

# Exclude specific folders from analysis
explorer = CodebaseExplorer(
    "/path/to/repo",
    exclude_folders=["tests", "vendor", "migrations"]
)

# Get directory tree (excluded folders are automatically filtered)
tree = await explorer.get_directory_tree(".", max_depth=3)

# Search for files (excluded folders are automatically filtered)
files = await explorer.search_files(".", "**/*.py")

# Read file contents
content = await explorer.read_file("src/main.py")

# Read multiple files
contents = await explorer.read_multiple_files(["src/a.py", "src/b.py"])

# Check if a path should be excluded
from pathlib import Path
should_exclude = explorer.should_exclude(Path("src/tests/unit.py"))
```

### Analyzers

```python
from pydantic import SecretStr
from skene_growth import ManifestAnalyzer, CodebaseExplorer
from skene_growth.llm import create_llm_client

# Initialize
codebase = CodebaseExplorer("/path/to/repo")
llm = create_llm_client(
    provider="openai",  # or "gemini", "anthropic"/"claude", "lmstudio", "ollama" (experimental), or "generic"
    api_key=SecretStr("your-api-key"),
    model_name="gpt-4o-mini",  # or "gemini-3-flash-preview" / "claude-haiku-4-5" / local model
)

# Run analysis
analyzer = ManifestAnalyzer()
result = await analyzer.run(
    codebase=codebase,
    llm=llm,
    request="Analyze this codebase for growth opportunities",
)

# Access results (the manifest is in result.data["output"])
manifest = result.data["output"]
print(manifest["tech_stack"])
print(manifest["current_growth_features"])
```

### Documentation Generator

```python
from pathlib import Path

from skene_growth import DocsGenerator, GrowthManifest

# Load manifest
manifest = GrowthManifest.model_validate_json(Path("growth-manifest.json").read_text())

# Generate docs
generator = DocsGenerator()
context_doc = generator.generate_context(manifest)
product_doc = generator.generate_product_docs(manifest)
```

## Growth Manifest Schema

The `growth-manifest.json` output contains:

```json
{
  "version": "1.0",
  "project_name": "my-app",
  "description": "A SaaS application",
  "tech_stack": {
    "framework": "Next.js",
    "language": "TypeScript",
    "database": "PostgreSQL",
    "auth": "NextAuth.js",
    "deployment": "Vercel"
  },
  "current_growth_features": [
    {
      "feature_name": "User Invites",
      "file_path": "src/components/InviteModal.tsx",
      "detected_intent": "referral",
      "confidence_score": 0.85,
      "growth_potential": ["viral_coefficient", "user_acquisition"]
    }
  ],
  "revenue_leakage": [
    {
      "issue": "Free tier allows unlimited usage without conversion prompts",
      "file_path": "src/pricing/tiers.py",
      "impact": "high",
      "recommendation": "Add usage limits or upgrade prompts to encourage paid conversions"
    }
  ],
  "growth_opportunities": [
    {
      "feature_name": "Social Sharing",
      "description": "No social sharing for user content",
      "priority": "high"
    }
  ],
  "generated_at": "2024-01-15T10:30:00Z"
}
```

### Product Docs Schema (v2.0)

When using `--product-docs` flag, the manifest includes additional fields:

```json
{
  "version": "2.0",
  "project_name": "my-app",
  "description": "A SaaS application",
  "tech_stack": { ... },
  "current_growth_features": [ ... ],
  "revenue_leakage": [ ... ],
  "growth_opportunities": [ ... ],
  "product_overview": {
    "tagline": "The easiest way to collaborate with your team",
    "value_proposition": "Simplify team collaboration with real-time editing and sharing.",
    "target_audience": "Remote teams and startups"
  },
  "features": [
    {
      "name": "Team Workspaces",
      "description": "Create dedicated spaces for your team to collaborate on projects.",
      "file_path": "src/features/workspaces/index.ts",
      "usage_example": "<WorkspaceCard workspace={workspace} />",
      "category": "Collaboration"
    }
  ],
  "generated_at": "2024-01-15T10:30:00Z"
}
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SKENE_API_KEY` | API key for LLM provider |
| `SKENE_PROVIDER` | LLM provider to use: `openai` (default), `gemini`, `anthropic`/`claude`, `lmstudio`, `ollama` (experimental), or `generic` |
| `SKENE_BASE_URL` | Base URL for OpenAI-compatible API endpoints (required for `generic` provider) |
| `SKENE_UPSTREAM_TOKEN` | Upstream API token for deploy push (overrides credentials file) |
| `LMSTUDIO_BASE_URL` | LM Studio server URL (default: `http://localhost:1234/v1`) |
| `OLLAMA_BASE_URL` | Ollama server URL (default: `http://localhost:11434/v1`) - Experimental |

## Requirements

- Python 3.11+
- **API key** (required for `analyze` command, except local LLMs):
  - OpenAI (default): https://platform.openai.com/api-keys
  - Gemini: https://aistudio.google.com/apikey
  - Anthropic: https://platform.claude.com/settings/keys
  - LM Studio: No API key needed (runs locally at http://localhost:1234)
  - Ollama (experimental): No API key needed (runs locally at http://localhost:11434)
  - Generic: API key depends on your endpoint (use `--base-url` to specify endpoint)

## Troubleshooting

### LM Studio: Context length error

If you see an error like:
```
Error code: 400 - {'error': 'The number of tokens to keep from the initial prompt is greater than the context length...'}
```

This means the model's context length is too small for the analysis. To fix:

1. In LM Studio, unload the current model
2. Go to **Developer > Load**
3. Click on **Context Length: Model supports up to N tokens**
4. Reload to apply changes

See: https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/237

### LM Studio: Connection refused

If you see a connection error, ensure:
- LM Studio is running
- A model is loaded and ready
- The server is running on the default port (http://localhost:1234)

If using a different port or host, set the `LMSTUDIO_BASE_URL` environment variable:
```bash
export LMSTUDIO_BASE_URL="http://localhost:8080/v1"
```

### Ollama: Connection refused (Experimental)

**Note:** Ollama support is experimental and has not been fully tested. Please report any issues.

If you see a connection error, ensure:
- Ollama is running (`ollama serve`)
- A model is pulled and available (`ollama list` to check)
- The server is running on the default port (http://localhost:11434)

If using a different port or host, set the `OLLAMA_BASE_URL` environment variable:
```bash
export OLLAMA_BASE_URL="http://localhost:8080/v1"
```

To get started with Ollama:
```bash
# Install Ollama (see https://ollama.com)
# Pull a model
ollama pull llama3.3

# Run the server (usually runs automatically)
ollama serve
```


## MCP Server

skene-growth includes an MCP server for integration with AI assistants.

Add this to your AI assistant configuration file:

```json
{
  "mcpServers": {
    "skene-growth": {
      "command": "uvx",
      "args": ["--from", "skene-growth[mcp]", "skene-growth-mcp"],
      "env": {
        "SKENE_API_KEY": "your-openai-api-key"
      }
    }
  }
}
```

See [docs/mcp-server.md](docs/mcp-server.md) for more detailed instructions.

## License

MIT
