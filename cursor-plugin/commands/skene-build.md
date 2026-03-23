---
name: skene-build
description: Build an implementation prompt for the selected growth loop. Generates context-aware instructions with code examples and testing checklists.
---

# Build Implementation Prompt

1. Invoke the `build-implementation` skill.
2. Run `uvx skene build --help` first to discover available flags and understand any interactive menus.
3. **Run autonomously.** Pipe the "show full prompt" option to get output in the terminal (typically `echo 3 | uvx skene build`). Read the prompt, then execute the implementation steps directly.
4. After implementing, suggest `/skene-status` to validate.
