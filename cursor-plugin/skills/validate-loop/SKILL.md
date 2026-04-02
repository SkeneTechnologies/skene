---
name: validate-loop
description: Check if growth loop requirements are actually implemented in the codebase. Use when the user says "validate", "check status", "skene status", "is it done", or "verify implementation".
---

# Validate Loop Implementation

Check implementation status via the Skene CLI.

## Agent behavior rules

- **Autonomous.** Run the CLI, present results, suggest next step. No mid-flow questions.
- **CLI is the source of truth.** If `uvx skene status` fails, report the error. Do NOT fabricate your own checklist.
- **User cannot type into agent terminals.** Pipe safe defaults for routine prompts. Kill stuck terminals.

## Steps

1. **Discover CLI options**
   Run `uvx skene status --help` to see available flags. Use only flags that appear in the output.

2. **Check for growth loops**
   `ls .skene/active-loop.json 2>/dev/null || ls skene-context/growth-loops/ 2>/dev/null`
   If missing: "No growth loop found. Run `/skene-plan` first." Stop.

3. **Run status check**
   Run `uvx skene status` with appropriate flags from --help output (e.g. path argument, `--context` if needed).
   If it fails, report error. Do NOT build your own checklist.

4. **Present CLI output**
   Present the engine status table from CLI output. For action features, **Detail** uses `Found in: <newest migration> (+N)` when the same trigger exists in multiple SQL files (`+N` = additional files beyond the one shown).

5. **Suggest next step**
   - All done → "Growth loop implemented. Run `/skene-deploy` for telemetry."
   - Gaps remain → "Remaining: [items]. Run `/skene-build` to continue."

## Error handling

- **CLI failure**: Report error, suggest fix.
- **Permission errors**: Give user the command for their terminal.

## Output

Status summary (done/partial/missing), what's left, next step.
