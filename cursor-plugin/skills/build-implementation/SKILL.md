---
name: build-implementation
description: Generate context-aware implementation prompts for a selected growth loop. Use when the user says "build", "implement", "generate code", "create prompt", or "how do I build this".
---

# Build Implementation Prompt

Generate implementation prompts via the Skene CLI. **The CLI generates the plan, not you.**

## Agent behavior rules

- **Autonomous.** Run the CLI, read the output, execute the implementation. No mid-flow questions.
- **CLI is the source of truth.** If `uvx skene build` fails, report the error. Do NOT write your own implementation plan as a substitute.
- **User cannot type into agent terminals.** The agent handles all CLI input.

## Steps

1. **Discover CLI options**
   Run `uvx skene build --help` to see available flags and understand any interactive prompts.

2. **Verify loop selection**
   `ls .skene/active-loop.json 2>/dev/null || ls skene-context/growth-loops/ 2>/dev/null`
   If missing: "Run `/skene-plan` first." Stop.

3. **Generate implementation prompt**
   The CLI may present a menu (e.g. "Select option [1/2/3/4]"). Always pipe the option that shows the full prompt in the terminal (typically `3` for "Show full prompt"):
   ```
   echo 3 | uvx skene build
   ```
   If the menu options differ from expected, check --help output or the terminal output to pick the "show/print prompt" option.

4. **Read the prompt**
   The CLI saves output to `skene-context/growth-loops/`. Read the full implementation prompt from the terminal output or that directory.

5. **Execute the prompt**
   Start implementing the steps from the CLI-generated prompt directly. Present a brief summary of what will be done, then execute. Break large implementations into logical chunks.

6. **Report completion**
   "Implementation complete. Run `/skene-status` to validate."

## Error handling

- **CLI failure**: Report error, suggest fix. Do NOT fabricate implementation plans.
- **Stuck on menu prompt**: Kill terminal, re-run with piped input.
- **Permission errors**: Give user the command for their terminal.

## Output

Summary of what was implemented + "Run `/skene-status` to validate."
