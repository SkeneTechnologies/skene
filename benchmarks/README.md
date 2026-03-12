# skene Benchmarking Suite

Compare `skene` pipeline output quality across LLM providers and models.

## Quick Start

```bash
# 1. Set API key(s) for the models you want to test
export GOOGLE_API_KEY="your-key"

# 2. Run with default config (uses tests/fixtures/sample_repo)
uv run benchmarks/run.py --skip-judge

# 3. Check results
ls benchmarks/results/
cat benchmarks/results/*/summary.md
```

## Configuration

Edit `benchmarks/config.toml` to configure codebases and models:

```toml
[settings]
runs_per_combo = 1

[[codebases]]
name = "my-project"
path = "./benchmarks/codebases/my-project"

[[models]]
name = "gemini-flash"
provider = "gemini"
model = "gemini-2.5-flash-preview-05-20"
api_key_env = "GOOGLE_API_KEY"

[[models]]
name = "claude-sonnet"
provider = "anthropic"
model = "claude-sonnet-4-5"
api_key_env = "ANTHROPIC_API_KEY"
```

API keys are read from environment variables specified by `api_key_env` — never hardcoded.

## CLI Options

```bash
uv run benchmarks/run.py [OPTIONS]

Options:
  --config PATH          Path to TOML config file (default: benchmarks/config.toml)
  --skip-judge           Skip LLM-as-judge evaluation (recommended for now)
  --evaluate-only PATH   Re-evaluate existing results directory (skip pipeline, re-run checks and report)
  --resume PATH          Resume a previous run: re-run only missing benchmarks, skip existing ones
```

`--evaluate-only` and `--resume` are mutually exclusive.

### Resuming failed runs

If a benchmark run fails partway (e.g. due to LLM quota limits), you can resume it:

1. Delete the run folders that failed or that you want to re-run:
   ```bash
   rm -rf benchmarks/results/<timestamp>/<codebase>/<model>/run-1
   ```
2. Resume with the same config:
   ```bash
   uv run benchmarks/run.py --resume benchmarks/results/<timestamp> \
       --config benchmarks/run-config.toml --skip-judge
   ```

Only the deleted runs will re-execute. Runs with an existing `metadata.json` are skipped.

## Output Structure

Each run creates a timestamped directory:

```
benchmarks/results/<timestamp>/
├── summary.json              # Machine-readable results
├── summary.md                # Human-readable comparison report
└── <codebase-name>/
    └── <model-name>/
        └── run-<n>/
            ├── growth-manifest.json
            ├── growth-template.json
            ├── growth-plan.md
            ├── .skene-build-prompt.md
            ├── growth-loops/*.json
            ├── cli-output.log        # Full CLI stdout/stderr
            └── metadata.json         # Timing and exit codes
```

## Evaluation

### Structural checks

Deterministic checks that run automatically:
- Pipeline completion (all steps exit code 0)
- File existence (manifest, template, plan, build prompt, growth loops)
- JSON validity
- Schema conformance (manifest validated against `GrowthManifest` model)
- Markdown minimum length

### Factual evaluation (ground truth)

Compares pipeline output against known, verifiable properties of each codebase. Requires a ground truth TOML file per codebase.

**Scored categories:**
- **tech_stack** — framework, language, database, auth, deployment, services detection accuracy
- **feature_detection** — recall of known growth features (matched by keyword or file pattern)
- **industry** — primary classification and secondary tag accuracy
- **file_references** — whether file paths in the manifest actually exist in the codebase

To enable, add `ground_truth` to your codebase config:

```toml
[[codebases]]
name = "my-project"
path = "./benchmarks/codebases/my-project"
ground_truth = "./benchmarks/ground_truth/my-project.toml"
```

See [Ground Truth Format](#ground-truth-format) for the TOML schema.

### LLM-as-judge (planned)

Future: uses a separate LLM to score output quality on criteria like completeness, actionability, and specificity.

## Ground Truth Format

Ground truth files live in `benchmarks/ground_truth/` and describe verifiable properties of a codebase. Only include properties you're confident about — unspecified fields are skipped during evaluation.

```toml
name = "my-project"
description = "Short description of the codebase"

[tech_stack]
framework = "Next.js"
language = "TypeScript"
database = "PostgreSQL"
auth = "Supabase Auth"
deployment = "Vercel"
package_manager = "npm"
services = ["Stripe", "Resend", "Vercel Analytics"]

[industry]
primary = "DevTools"
acceptable_alternatives = ["SaaS", "Productivity"]
expected_tags = ["B2B", "SaaS"]

[[expected_features]]
name = "billing"
description = "Stripe subscription billing"
file_patterns = ["subscriptions", "stripe"]
keywords = ["billing", "subscription", "stripe", "payment"]

[[expected_features]]
name = "team_invites"
description = "Workspace invitation system"
file_patterns = ["invitations", "members"]
keywords = ["invitation", "invite", "team", "collaboration"]

# Key files that should be referenced in manifest output
notable_files = [
    "app/actions/subscriptions.ts",
    "app/actions/invitations.ts",
]
```

**Matching rules:**
- Tech stack uses fuzzy matching (case-insensitive, handles "Next.js" vs "NextJS")
- Feature detection matches by keyword in feature name/description OR file pattern in detected file paths
- Industry primary accepts the expected value or any listed alternative
- File reference validity passes if ≥50% of manifest file paths exist in the codebase

## Adding Codebases

See `benchmarks/codebases/README.md` for instructions on populating sample codebases.
