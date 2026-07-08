---
name: skene-deploy
description: Deploy telemetry upstream. Expects skene-context/engine.yaml, skene-context/feature-registry.json (or configured output_dir; legacy skene/feature-registry.json still works), and supabase/migrations/*_skene_triggers.sql; push uploads the package to Skene Cloud.
---

# Deploy Telemetry

1. Invoke the `deploy-telemetry` skill.
2. Run `uvx skene push --help` first to discover available flags.
3. **Run autonomously** except: ask the user to confirm before `uvx skene push` (upstream deploy — genuine blocker). The artifacts (`engine.yaml`, `*_skene_triggers.sql`) must already exist.
4. Report engine, feature registry (if included), and trigger migration sent; suggest `/skene-status`.
