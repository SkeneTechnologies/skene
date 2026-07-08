# Python API

Programmatic access to skene's codebase exploration, configuration, LLM client, and journey models.

## Quick example

```python
from pathlib import Path
import yaml

from skene import CodebaseExplorer
from skene.analyzers.journey.models import Journey

# Sandboxed access to a codebase
explorer = CodebaseExplorer(Path("/path/to/repo"))

# Load and validate a journey.yaml produced by `skene analyse-journey`
journey = Journey.model_validate(
    yaml.safe_load(Path("skene-context/journey.yaml").read_text())
)
print(journey.product.name)
for stage in journey.stages:
    print(stage.name, [m.name for m in stage.milestones])
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

## Configuration

```python
from skene import Config, load_config

# Load config from files + env vars
config = load_config()

# Access properties
config.api_key       # str | None
config.provider      # str (default: "openai")
config.model         # str (auto-determined if not set)
config.output_dir    # str (default: "./skene-context"; legacy "./skene" auto-detected)
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

## Journey models

The `journey.yaml` schema is defined by Pydantic v2 models in `skene.analyzers.journey.models`. They are validated end-to-end before the file is written by `skene analyse-journey`.

```python
from skene.analyzers.journey.models import (
    Journey,        # The whole document
    Product,        # Product metadata (name, description, generated_at, source_commit)
    Stage,          # A lifecycle stage containing milestones and KPIs
    Milestone,      # A user-facing milestone with evidence
    Kpi,            # A stage KPI
    KpiDerivation,  # How a KPI is derived from tables/events
    Layer,          # A named layer spanning multiple stages
    Connector,      # A cross-stage link between milestones
    Evidence,       # Re-exported from skene.schema.milestone
    EvidenceSource, # Re-exported from skene.schema.milestone
    TriggerType,    # Enum: email, scheduled, webhook, event_bus, unknown
    ConnectorStyle, # Enum: solid, dashed, dotted
    KpiUnit,        # Enum: percentage, count, duration_days, duration_hours, ratio, currency
)
```

### Journey fields

| Field | Type |
|-------|------|
| `product` | `Product` |
| `layers` | `list[Layer]` |
| `stages` | `list[Stage]` (min 1) |
| `connectors` | `list[Connector]` |

Model validators enforce unique stage/layer/connector IDs, unique stage orders, and that layers and connectors reference real stages/milestones.

### Stage fields

| Field | Type |
|-------|------|
| `id` | `str` (snake_case ID) |
| `order` | `int` (>= 1) |
| `name` | `str` |
| `subtitle` | `str \| None` |
| `milestones` | `list[Milestone]` (min 1, unique IDs and orders) |
| `kpis` | `list[Kpi]` (unique IDs) |

### Milestone fields

| Field | Type |
|-------|------|
| `id` | `str` (snake_case ID) |
| `order` | `int` (>= 1) |
| `name` | `str` |
| `description` | `str` |
| `evidence` | `list[Evidence]` (min 1) |
| `tracked_event` | `str \| None` |
| `confidence` | `float` (0.0–1.0, default 1.0) |

### Connector fields

| Field | Type |
|-------|------|
| `id` | `str` (snake_case ID) |
| `from` | `str` (`"<stage_id>.<milestone_id>"`) |
| `to` | `str` (milestone ref or the literal `"unknown"`) |
| `label` | `str` |
| `trigger_type` | `TriggerType` |
| `style` | `ConnectorStyle` (default `dashed`) |
| `confidence` | `float` (0.0–1.0, default 1.0) |
| `evidence` | `list[Evidence]` (min 1) |

### Serialization

```python
from skene.analyzers.journey import serialize

yaml_text = serialize.to_yaml(journey)   # Render Journey to YAML
json_text = serialize.to_json(journey)   # Render Journey to JSON
serialize.write(journey, path)           # Write journey.yaml to disk
```

### Journey pipeline

The rest of the journey machinery lives alongside the models and is orchestrated by `skene.core.journey`:

- `skene.analyzers.journey.merge` — `merge_candidates` deduplicates milestone candidates from the code and schema agents
- `skene.analyzers.journey.classify` — `classify_milestone` / `classify_all` assign candidates to lifecycle stages
- `skene.analyzers.journey.assemble` — `assemble_journey` builds the final validated `Journey`
- `skene.analyzers.schema_parsers` — `parse_schema_dir` (SQL files) and `introspect_db` (live PostgreSQL) produce the schema input

## Feature registry

```python
from skene.feature_registry import (
    load_feature_registry,              # Load registry from disk
    write_feature_registry,             # Write registry to disk
    merge_features_into_registry,       # Merge new features with existing registry
    upsert_registry_from_engine,        # Upsert registry entries from engine.yaml features
    export_registry_to_format,          # Export to json, csv, or markdown
    derive_feature_id,                  # Convert feature name to snake_case ID
    compute_loop_ids_by_feature,        # Map feature_id -> list of loop_ids
)
```

### Key functions

| Function | Description |
|----------|-------------|
| `merge_features_into_registry(new_features, registry)` | Merges new features: adds new, updates matched, archives missing |
| `upsert_registry_from_engine(engine_doc, registry_path)` | Upserts feature-registry entries from `engine.yaml` features |
| `export_registry_to_format(registry, format)` | Exports to `"json"`, `"csv"`, or `"markdown"` |

## Engine and migrations

```python
from skene.engine import (
    load_engine_document,               # Load engine.yaml from the bundle dir
    write_engine_document,              # Write engine.yaml to the bundle dir
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
    collect_push_files,                 # [{path, content}] — full bundle under output_dir + trigger SQL
    build_push_manifest,                # Create push manifest with checksum over files
    push_to_upstream,                   # POST {manifest, files} to /api/v1/push
)
```
