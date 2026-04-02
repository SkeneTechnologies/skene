# Python API

Programmatic access to skene's codebase analysis, manifest generation, and documentation tools.

## Quick example

```python
import asyncio
from pathlib import Path
from pydantic import SecretStr
from skene import CodebaseExplorer, ManifestAnalyzer
from skene.llm import create_llm_client

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
from skene import CodebaseExplorer, DEFAULT_EXCLUDE_FOLDERS

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
from skene import ManifestAnalyzer

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
from skene import TechStackAnalyzer

analyzer = TechStackAnalyzer()
result = await analyzer.run(codebase=codebase, llm=llm)
tech_stack = result.data["output"]
```

### GrowthFeaturesAnalyzer

Identifies existing growth features in a codebase.

```python
from skene import GrowthFeaturesAnalyzer

analyzer = GrowthFeaturesAnalyzer()
result = await analyzer.run(codebase=codebase, llm=llm)
features = result.data["output"]
```

## Configuration

```python
from skene import Config, load_config

# Load config from files + env vars
config = load_config()

# Access properties
config.api_key       # str | None
config.provider      # str (default: "openai")
config.model         # str (auto-determined if not set)
config.output_dir    # str (default: "./skene-context")
config.debug         # bool (default: False)
config.exclude_folders  # list[str] (default: [])
config.base_url      # str | None
config.upstream      # str | None (upstream workspace URL)

# Get/set arbitrary keys
config.get("api_key", default=None)
config.set("provider", "gemini")
```

### Upstream credentials

```python
from skene.config import (
    save_upstream_to_config,    # Save upstream URL, workspace, API key to .skene.config
    remove_upstream_from_config,# Remove upstream credentials from .skene.config
    resolve_upstream_token,     # Resolve token from env/config
)
```

## LLM Client

```python
from pydantic import SecretStr
from skene.llm import create_llm_client, LLMClient

client: LLMClient = create_llm_client(
    provider="openai",          # openai, gemini, anthropic, ollama, lmstudio, generic
    api_key=SecretStr("key"),
    model="gpt-4o",
    base_url=None,              # Required for generic provider
    debug=False,                # Log LLM I/O to ~/.local/state/skene/debug/
)
```

## Manifest schemas

All schemas are Pydantic v2 models. See [Manifest schema reference](manifest-schema.md) for full field details.

```python
from skene import (
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

## Feature registry

```python
from skene.feature_registry import (
    load_feature_registry,              # Load registry from disk
    write_feature_registry,             # Write registry to disk
    merge_features_into_registry,       # Merge new features with existing registry
    merge_registry_and_enrich_manifest, # Full registry + manifest enrichment pipeline
    load_features_for_build,            # Load active features for build command
    export_registry_to_format,          # Export to json, csv, or markdown
    derive_feature_id,                  # Convert feature name to snake_case ID
    compute_loop_ids_by_feature,        # Map feature_id -> list of loop_ids
)
```

### Key functions

| Function | Description |
|----------|-------------|
| `merge_features_into_registry(new_features, registry)` | Merges new features: adds new, updates matched, archives missing |
| `merge_registry_and_enrich_manifest(manifest, engine_features, output_path)` | Full pipeline: loads/maps engine features, writes registry, enriches manifest |
| `upsert_registry_from_engine(engine_doc, registry_path)` | Upserts feature-registry entries from `engine.yaml` features |
| `load_features_for_build(context_dir)` | Returns active features list for the build command |
| `export_registry_to_format(registry, format)` | Exports to `"json"`, `"csv"`, or `"markdown"` |

## Engine and migrations

```python
from skene.engine import (
    load_engine_document,               # Load skene/engine.yaml
    write_engine_document,              # Write skene/engine.yaml
    merge_engine_documents,             # Merge delta by key
    parse_source_to_db_event,           # Parse schema.table.operation source
    engine_features_to_loop_definitions # Adapter for migration builder
)

from skene.growth_loops.push import (
    ensure_base_schema_migration,       # Check, build, update base schema (creates or overwrites)
    build_loops_to_supabase,            # Build Supabase migrations from trigger definitions
    build_migration_sql,                # Generate migration SQL
    find_trigger_migration,             # Latest telemetry migration path (*_skene_triggers.sql + legacy names)
    write_migration,                    # Write timestamped *_skene_triggers.sql (default migration_name)
    push_to_upstream,                   # Push to upstream API
)

from skene.growth_loops.upstream import (
    validate_token,                     # Validate token via upstream API
    build_package,                      # engine_yaml + feature_registry_json + trigger_sql
    build_push_manifest,                # Create push manifest with checksum
    push_to_upstream,                   # POST package to /api/v1/deploys
)
```

## Plan decline

```python
from skene.planner.decline import (
    decline_plan,           # Archive a declined plan with executive summary only
    load_declined_plans,    # Load recent declined plans for reference
)
```

## Documentation generation

```python
from skene import DocsGenerator, GrowthManifest

manifest = GrowthManifest.model_validate_json(open("growth-manifest.json").read())

generator = DocsGenerator()
context_doc = generator.generate_context_doc(manifest)
product_doc = generator.generate_product_docs(manifest)
```

The `PSEOBuilder` class generates programmatic SEO content from manifests.

## Strategy framework

The analysis pipeline is built on a composable strategy framework:

```python
from skene.strategies import (
    AnalysisStrategy,    # Base strategy class
    AnalysisResult,      # Result container with data + metadata
    AnalysisMetadata,    # Timing, token usage, step info
    AnalysisContext,     # Shared context between steps
    MultiStepStrategy,   # Chains multiple steps together
)

from skene.strategies.steps import (
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
from skene.planner import Planner
from skene.planner.schema import GrowthPlan, TechnicalExecution, PlanSection
```

The `Planner` class generates growth plans from manifests and templates. It is used internally by the `plan` CLI command.

### GrowthPlan schema

| Field | Type | Description |
|-------|------|-------------|
| `executive_summary` | `str` | High-level summary focused on first-time activation |
| `sections` | `list[PlanSection]` | Plan sections (dynamic, driven by step definitions) |
| `technical_execution` | `TechnicalExecution` | Technical Execution blueprint |

### TechnicalExecution fields

| Field | Type | Description |
|-------|------|-------------|
| `overview` | `str` | 1-2 sentence overview with confidence |
| `what_we_building` | `str` | Short numbered list (3-5 items) of what we're building |
| `tasks` | `str` | Most important technical tasks only, short numbered list |
| `data_triggers` | `str` | Events/conditions that trigger the flow |
| `success_metrics` | `str` | Primary success metrics |

### PlanSection fields

| Field | Type | Description |
|-------|------|-------------|
| `title` | `str` | Section heading, e.g. `"The Next Action"` |
| `content` | `str` | Free-form markdown content |

### Helper functions

- `render_plan_to_markdown(plan, generated_at, project_name=None)` — Render a `GrowthPlan` to the council memo markdown format. Include `project_name` only when from manifest file.
- `parse_plan_json(response)` — Parse an LLM response (with optional code fences) into a validated `GrowthPlan`
