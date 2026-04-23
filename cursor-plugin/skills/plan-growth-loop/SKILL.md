---
name: plan-growth-loop
description: Generate prioritized growth loops with implementation roadmaps based on codebase analysis. Use when the user says "plan", "growth loops", "prioritize", "what should I build", or "roadmap".
---

# Plan Growth Loop

Generate prioritized growth loops from the Skene CLI. **The CLI does the planning, not you.**

## Agent behavior rules

- **Autonomous.** Run the CLI, present results, suggest next step. No mid-flow questions unless there's a genuine blocker.
- **CLI is the source of truth.** If `uvx skene plan` fails, report the error. Do NOT generate your own growth loops.
- **User cannot type into agent terminals.** Pipe safe defaults for routine prompts. Kill stuck terminals and re-run.

## Steps

1. **Discover CLI options**
   Run `uvx skene plan --help` to see available flags. Use only flags that appear in the output.

2. **Verify analysis exists**
   `ls .skene/analysis/ 2>/dev/null || ls skene/ 2>/dev/null || ls skene-context/ 2>/dev/null`
   If missing: "Run `/skene-analyze` first." Stop.

3. **Generate growth plan**
   Run `uvx skene plan` with appropriate flags from --help output.
   If it fails, report error. Do NOT make up growth loops.

4. **Present CLI output**
   Read results from `.skene/plans/`, `skene/growth-loops/`, or `skene-context/growth-loops/` and present loops by priority.

5. **Help user choose**
   Ask which loop to implement — this is the one genuine decision point.

6. **Store selection**
   Use the appropriate CLI flag from --help to store the selection (e.g. `--select`). If the command prompts for input, pipe the answer. If no select flag exists, write to `.skene/active-loop.json` directly.

7. **Next step**
   "Run `/skene-build` to generate the implementation plan."

## Error handling

- **CLI failure**: Report error, suggest fix. Do NOT fabricate growth loops.
- **Permission errors**: Give user the command for their terminal.

## Output

Loops found, selection stored, next step (`/skene-build`).
