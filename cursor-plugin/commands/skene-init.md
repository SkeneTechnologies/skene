---
name: skene-init
description: Initialize Skene configuration for this project. Creates .skene.config (TOML), sets up provider and API key (or SKENE_API_KEY), and runs validation.
---

# Initialize Skene

1. Invoke the `initialize-config` skill.
2. Run `uvx skene config --help` first to discover available flags. Do not assume flags exist.
3. **Run autonomously.** Detect existing config, env vars, user-level config. Fix mismatches, apply defaults. Handle all CLI prompts silently. Only ask the user if API key is missing everywhere.
4. If a terminal gets stuck on a prompt, kill it and re-run with piped input.
5. **End with one line:** "Skene init complete. Provider: X, model: Y. Run `/skene-analyze` next."
