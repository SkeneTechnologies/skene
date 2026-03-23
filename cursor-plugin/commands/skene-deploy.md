---
name: skene-deploy
description: Deploy telemetry and analytics infrastructure. Creates Supabase migrations, sets up event tracking, and generates client code.
---

# Deploy Telemetry

1. Invoke the `deploy-telemetry` skill.
2. Run `uvx skene push --help` first to discover available flags.
3. **Run autonomously** except: ask user to confirm before running `uvx skene push` (it writes migration files — genuine blocker).
4. Report the generated migration file and suggest `/skene-status`.
