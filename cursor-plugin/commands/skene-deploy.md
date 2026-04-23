---
name: skene-deploy
description: Deploy telemetry upstream after build. Expects skene/engine.yaml, skene/feature-registry.json (or configured output_dir; legacy skene-context/feature-registry.json still works), and supabase/migrations/*_skene_triggers.sql; push uploads the package to Skene Cloud.
---

# Deploy Telemetry

1. Invoke the `deploy-telemetry` skill.
2. Run `uvx skene push --help` first to discover available flags.
3. **Run autonomously** except: ask the user to confirm before `uvx skene push` (upstream deploy — genuine blocker). Ensure `uvx skene build` has been run so `*_skene_triggers.sql` exists.
4. Report engine, feature registry (if included), and trigger migration sent; suggest `/skene-status`.
