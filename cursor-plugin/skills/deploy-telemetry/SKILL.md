---
name: deploy-telemetry
description: Set up analytics and tracking infrastructure for growth loops. Use when the user says "deploy telemetry", "set up analytics", "tracking", "events", "push to supabase", or "skene push".
---

# Deploy Telemetry

Set up analytics infrastructure via the Skene CLI.

## Agent behavior rules

- **Autonomous.** Run CLI commands, report results, suggest next step. No mid-flow questions except for genuine blockers.
- **CLI is the source of truth.** Do NOT fabricate migration schemas or client code if the CLI fails.
- **User cannot type into agent terminals.** Pipe safe defaults for routine prompts. Kill stuck terminals.
- **Upstream push can be a genuine blocker.** Ask the user in chat to confirm before running `uvx skene push` — it POSTs `skene/engine.yaml`, `{output_dir}/feature-registry.json` when present, and the latest trigger migration to Skene Cloud (it does not generate SQL; run `uvx skene build` first if artifacts are missing).

## Steps

1. **Discover CLI options**
   Run `uvx skene push --help` to see available flags. Use only flags that appear in the output.

2. **Verify prerequisites**
   - `skene/engine.yaml` must exist; trigger SQL lives under `supabase/migrations/` as `*_skene_triggers.sql` after `uvx skene build` (older projects may use legacy `*skene_trigger*` / `*skene_telemetry*` filenames).
   - Feature registry: default `skene/feature-registry.json` (or `{output_dir}` from config; legacy `skene-context/feature-registry.json` auto-detected). If missing, push still runs but omits the registry until `build` creates it.
   - If engine or migrations are missing: tell the user to run `uvx skene build` first, then retry deploy.
   - `ls supabase/ 2>/dev/null` — if missing: "No Supabase directory. Set up Supabase first."

3. **Ask user to confirm**
   Tell the user: "`uvx skene push` uploads engine, feature-registry.json (if present), and latest `*_skene_triggers.sql` to upstream. Proceed?"
   Wait for confirmation.

4. **Run push**
   After user confirms, run `uvx skene push` with appropriate flags from --help output.
   Report which migration file was packaged (latest eligible under `supabase/migrations/`) and that upstream received the deploy.

5. **Report result**
   Engine path, registry path (if packaged), trigger migration path, next step: apply DB migrations locally if needed (`supabase db push`), then "Run `/skene-status` to verify."

6. **Privacy reminder** (one line)
   "Remember GDPR/CCPA consent management before production tracking."

## Error handling

- **CLI failure**: Report error, suggest fix.
- **Permission errors**: Give user the command for their terminal.

## Output

Deploy result (or error), paths used, next step (`/skene-status`).
