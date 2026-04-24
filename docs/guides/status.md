# Status Command

The `status` command validates `skene-context/engine.yaml` and checks whether action-enabled features have matching trigger/function artifacts in `supabase/migrations`.

## Prerequisites

Before running `status`, you need:

- A `skene-context/engine.yaml` file (generated or updated by `build`)
- Trigger migrations in `supabase/migrations/` if your engine features include `action`

## Basic usage

Check engine/migration status for the current project:

```bash
uvx skene status
```

By default, `PATH` is the project root and `status` checks `skene-context/engine.yaml`.

Specify a different project root:

```bash
uvx skene status ./my-project
```

Point to a context directory (deprecated compatibility behavior):

```bash
uvx skene status --context ./my-project/skene
```

The legacy `--find-alternatives` options are currently ignored for engine validation.

## Flag reference

| Flag | Short | Description |
|------|-------|-------------|
| `--context PATH` | `-c` | Deprecated. If set to a Skene bundle directory (`skene-context/` or legacy `skene/`), parent is treated as project root. |
| `--find-alternatives` | | Deprecated for engine status checks; currently ignored. |
| `--api-key TEXT` | | Deprecated for engine status checks; currently ignored. |
| `--provider TEXT` | `-p` | Deprecated for engine status checks; currently ignored. |
| `--model TEXT` | `-m` | Deprecated for engine status checks; currently ignored. |

## How it works

The status command follows a three-step pipeline:

### Step 1: Load engine file

The command loads `skene-context/engine.yaml` from project root. If `--context` points to a Skene bundle directory (`.../skene-context` or `.../skene`), it uses the parent directory as project root.

### Step 2: Validate structure and source fields

The command validates:

- Engine YAML is parseable and well-formed
- Subject/feature keys are unique
- Feature `source` values match `schema.table.operation`

### Step 3: Validate migration presence for action features

For each feature:

- If `action` exists: checks for matching `skene_growth_fn_*` and `skene_growth_trg_*` identifiers in migration SQL files. When several migrations contain the same trigger, the report lists the latest migration filename (by sort order) and appends `(+N)` where `N` is the number of additional matching files.
- If `action` is absent: reports code-only mode (no trigger required).

## Example output

```
Project root: /path/to/project

Engine Status
Feature             Source                    Mode      Status   Detail
New Document Email  public.documents.insert   action    ok       Found in: 20260304151537_skene_triggers.sql
Warm Welcome Copy   public.users.insert       code-only ok       Code-only feature (no action): trigger migration not required
```

## Next steps

- [Build](build.md) -- Generate/merge `skene-context/engine.yaml` and trigger migrations
- [Push](push.md) -- Push pre-generated artifacts upstream
- [CLI Reference](../reference/cli.md) -- Full reference for all commands and flags
