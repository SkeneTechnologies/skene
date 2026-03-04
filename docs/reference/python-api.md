# Python API

Programmatic access to skene-growth's codebase analysis, manifest generation, and documentation tools.

## Quick example

```python
import asyncio
from pathlib import Path
from pydantic import SecretStr
from skene_growth import CodebaseExplorer, ManifestAnalyzer
from skene_growth.llm import create_llm_client

async def main():
    codebase = CodebaseExplorer(Path("/path/to/repo"))
    llm = create_llm_client(
        provider="openai",
        api_key=SecretStr("your-api-key"),
        model="gpt-4o",
    )

    analyzer = ManifestAnalyzer()
    result = await analyzer.run(
        codebase=codebase,
        llm=llm,
        request="Analyze this codebase for growth opportunities",
    )

    manifest = result.data["output"]
    print(manifest["tech_stack"])
    print(manifest["current_growth_features"])

asyncio.run(main())
```

## CodebaseExplorer

Safe, sandboxed access to codebase files. Automatically excludes common build/cache directories.

```python
from pathlib import Path
from skene_growth import CodebaseExplorer, DEFAULT_EXCLUDE_FOLDERS

# Create with default exclusions
explorer = CodebaseExplorer(Path("/path/to/repo"))

# Create with custom exclusions (merged with defaults)
explorer = CodebaseExplorer(
    Path("/path/to/repo"),
    exclude_folders=["tests", "vendor", "migrations"]
)
```

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `await get_directory_tree(start_path, max_depth)` | `dict` | Directory tree with file counts |
| `await search_files(start_path, pattern)` | `dict` | Files matching glob pattern |
| `await read_file(file_path)` | `str` | File contents |
| `await read_multiple_files(file_paths)` | `dict` | Multiple file contents |
| `should_exclude(path)` | `bool` | Check if a path should be excluded |

### Related

- `build_directory_tree` — Standalone function for building directory trees
- `DEFAULT_EXCLUDE_FOLDERS` — List of default excluded folder names

## Analyzers

### ManifestAnalyzer

Runs a full codebase analysis and produces a growth manifest.

```python
from skene_growth import ManifestAnalyzer

analyzer = ManifestAnalyzer()
result = await analyzer.run(
    codebase=codebase,
    llm=llm,
    request="Analyze this codebase for growth opportunities",
)

manifest = result.data["output"]
```

### TechStackAnalyzer

Detects the technology stack of a codebase.

```python
from skene_growth import TechStackAnalyzer

analyzer = TechStackAnalyzer()
result = await analyzer.run(codebase=codebase, llm=llm)
tech_stack = result.data["output"]
```

### GrowthFeaturesAnalyzer

Identifies existing growth features in a codebase.

```python
from skene_growth import GrowthFeaturesAnalyzer

analyzer = GrowthFeaturesAnalyzer()
result = await analyzer.run(codebase=codebase, llm=llm)
features = result.data["output"]
```

## Configuration

```python
from skene_growth import Config, load_config

# Load config from files + env vars
config = load_config()

# Access properties
config.api_key       # str | None
config.provider      # str (default: "openai")
config.model         # str (auto-determined if not set)
config.output_dir    # str (default: "./skene-context")
config.verbose       # bool (default: False)
config.debug         # bool (default: False)
config.exclude_folders  # list[str] (default: [])
config.base_url      # str | None

# Get/set arbitrary keys
config.get("api_key", default=None)
config.set("provider", "gemini")
```

## LLM Client

```python
from pydantic import SecretStr
from skene_growth.llm import create_llm_client, LLMClient

client: LLMClient = create_llm_client(
    provider="openai",          # openai, gemini, anthropic, ollama, lmstudio, generic
    api_key=SecretStr("key"),
    model="gpt-4o",
    base_url=None,              # Required for generic provider
    debug=False,                # Log LLM I/O to .skene-growth/debug/
)
```

## Manifest schemas

All schemas are Pydantic v2 models. See [Manifest schema reference](manifest-schema.md) for full field details.

```python
from skene_growth import (
    GrowthManifest,     # v1.0 manifest
    DocsManifest,       # v2.0 manifest (extends GrowthManifest)
    TechStack,
    GrowthFeature,
    GrowthOpportunity,
    IndustryInfo,
    ProductOverview,    # v2.0 only
    Feature,            # v2.0 only
)
```

### GrowthManifest fields

| Field | Type |
|-------|------|
| `version` | `str` (`"1.0"`) |
| `project_name` | `str` |
| `description` | `str \| None` |
| `tech_stack` | `TechStack` |
| `industry` | `IndustryInfo \| None` |
| `current_growth_features` | `list[GrowthFeature]` |
| `growth_opportunities` | `list[GrowthOpportunity]` |
| `revenue_leakage` | `list[RevenueLeakage]` |
| `generated_at` | `datetime` |

### DocsManifest additional fields

| Field | Type |
|-------|------|
| `version` | `str` (`"2.0"`) |
| `product_overview` | `ProductOverview \| None` |
| `features` | `list[Feature]` |

## Documentation generation

```python
from skene_growth import DocsGenerator, GrowthManifest

manifest = GrowthManifest.model_validate_json(open("growth-manifest.json").read())

generator = DocsGenerator()
context_doc = generator.generate_context_doc(manifest)
product_doc = generator.generate_product_docs(manifest)
```

The `PSEOBuilder` class generates programmatic SEO content from manifests.

## Strategy framework

The analysis pipeline is built on a composable strategy framework:

```python
from skene_growth.strategies import (
    AnalysisStrategy,    # Base strategy class
    AnalysisResult,      # Result container with data + metadata
    AnalysisMetadata,    # Timing, token usage, step info
    AnalysisContext,     # Shared context between steps
    MultiStepStrategy,   # Chains multiple steps together
)

from skene_growth.strategies.steps import (
    AnalysisStep,        # Base step class
    SelectFilesStep,     # Select relevant files for analysis
    ReadFilesStep,       # Read file contents
    AnalyzeStep,         # Send to LLM for analysis
    GenerateStep,        # Generate structured output
)
```

These classes are primarily used internally by the analyzers but can be composed for custom analysis pipelines.

## Planner

```python
from skene_growth.planner import Planner
from skene_growth.planner.schema import GrowthPlan, TechnicalExecution, PlanSection
```

The `Planner` class generates growth plans from manifests and templates. It is used internally by the `plan` CLI command.

### GrowthPlan schema

| Field | Type | Description |
|-------|------|-------------|
| `executive_summary` | `str` | High-level summary focused on first-time activation |
| `sections` | `list[PlanSection]` | Numbered memo sections (1-6) |
| `technical_execution` | `TechnicalExecution` | Section 7: Technical Execution |
| `memo` | `str` | Section 8: The closing confidential engineering memo |

### TechnicalExecution fields

| Field | Type | Description |
|-------|------|-------------|
| `next_build` | `str` | What activation loop to build next |
| `confidence` | `str` | Confidence level, e.g. `"85%"` |
| `exact_logic` | `str` | Specific flow changes for first-action completion |
| `data_triggers` | `str` | Events indicating first meaningful action |
| `stack_steps` | `str` | Tools, scripts, or structural changes required |
| `sequence` | `str` | Now / Next / Later priorities |

### PlanSection fields

| Field | Type | Description |
|-------|------|-------------|
| `title` | `str` | Section heading, e.g. `"The Next Action"` |
| `content` | `str` | Free-form markdown content |

### Helper functions

- `render_plan_to_markdown(plan, project_name, generated_at)` — Render a `GrowthPlan` to the council memo markdown format
- `parse_plan_json(response)` — Parse an LLM response (with optional code fences) into a validated `GrowthPlan`
