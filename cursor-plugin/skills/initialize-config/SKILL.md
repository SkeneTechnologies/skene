---
name: initialize-config
description: Set up Skene configuration for a project. Use when starting a new PLG analysis, when .skene.config is missing, or when the user says "skene init", "set up skene", or "configure skene".
---

# Initialize Skene Configuration

Set up Skene automatically. The user runs `/skene-init`, everything gets configured, and they see a one-line summary. **Zero questions unless something is genuinely missing and cannot be inferred.**

**Config reference**: [Configuration guide](https://www.skene.ai/resources/docs/skene/guides/configuration).

## Design principle

Make init invisible. Detect everything from existing config, env vars, and user-level config. Only ask the user if the agent truly cannot figure it out (e.g. API key missing everywhere).

## Steps

1. **Discover CLI options**
   Run `uvx skene config --help` to see what flags are available. Use only flags that appear in the output.

2. **Check what already exists** (run in parallel where possible):
   - `ls .skene.config 2>/dev/null` — project config
   - `ls ~/.config/skene/config 2>/dev/null` — user-level config
   - `echo n | uvx skene config --show` — full resolved config (piped to avoid blocking)
   - `printenv SKENE_API_KEY SKENE_PROVIDER 2>/dev/null` — env vars

3. **Decide what to do** (no user interaction needed):

   **Case A — Config exists and is valid** (provider set, API key present, provider/model match):
   Done. Report summary.

   **Case B — Config exists but has issues** (provider/model mismatch, missing API key, etc.):
   Fix what you can automatically:
   - Provider/model mismatch → update `.skene.config` with correct defaults.
   - API key missing from file but `SKENE_API_KEY` in env → fine, note it.
   - API key missing everywhere → ask user: "Set `SKENE_API_KEY` in your environment, then re-run `/skene-init`."

   **Case C — No config at all**:
   - Run `uvx skene config --init` (check --help first to confirm this flag exists).
   - If that fails with permission error, write `.skene.config` TOML directly.
   - Infer provider from env vars or default to `openai`.
   - Validate with `echo n | uvx skene config --show`.

4. **Final validation**
   ```
   echo n | uvx skene config --show
   ```
   Confirm provider, model, API key. If good, report.

5. **Report result**
   "Skene init complete. Provider: X, model: Y. Run `/skene-analyze` next."

## Terminal rules

The user CANNOT type into agent-spawned terminals. The agent handles ALL input.

- Always pipe `echo n` to `uvx skene config --show` to skip the edit prompt.
- NEVER run `uvx skene config` (no flags) — multi-step interactive. Write `.skene.config` directly.
- Stuck terminal: kill the process and re-run with piped input.
- Genuine blockers only: API key missing everywhere is the only thing that requires user action.

## Error handling

- **Permission error**: Write `.skene.config` manually. If `uvx` itself can't run, tell user to run `pip install uv` in their terminal.
- **API key missing everywhere**: Ask user to set `SKENE_API_KEY`.
- **Provider/model mismatch**: Fix automatically.

## Output

One line: "Skene init complete. Provider: X, model: Y. Run `/skene-analyze` next."
