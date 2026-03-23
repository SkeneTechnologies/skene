---
name: skene-status
description: Check implementation status of the active growth loop. Validates required features, telemetry deployment, and test coverage.
---

# Check Implementation Status

1. Invoke the `validate-loop` skill.
2. Run `uvx skene status --help` first to discover available flags.
3. **Run autonomously.** Present the CLI's implementation checklist. No mid-flow questions.
4. Highlight gaps, suggest next step (`/skene-build` or `/skene-deploy`).
