---
name: skene-status
description: Check implementation status from skene/engine.yaml. Validates features, action vs code-only mode, and that trigger/function SQL exists in migrations; detail shows latest matching file and (+N) if duplicates.
---

# Check Implementation Status

1. Invoke the `validate-loop` skill.
2. Run `uvx skene status --help` first to discover available flags.
3. **Run autonomously.** Present the CLI engine status table. No mid-flow questions.
4. Explain the Detail column: for action features, "Found in" lists the newest matching migration basename; `(+N)` means N other migration files also contain that trigger.
5. Highlight gaps, suggest next step (`/skene-build` or `/skene-deploy`).
