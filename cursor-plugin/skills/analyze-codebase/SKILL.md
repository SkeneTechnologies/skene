---
name: analyze-codebase
description: Run comprehensive PLG analysis on a codebase to detect tech stack, existing growth features, and revenue opportunities. Use when the user says "analyze", "scan", "audit codebase", or "find growth opportunities".
---

# Analyze Codebase

Run the Skene CLI to analyze the codebase. **The CLI does the analysis, not you.**

## Critical rule

**Do NOT substitute your own PLG analysis, findings, or guesses if the CLI fails.** Run the CLI, present its output on success, report the error on failure. That's it.

## Agent behavior rules

- **Autonomous.** Run the CLI, present results, suggest next step. No mid-flow questions.
- **User cannot type into agent terminals.** The agent handles all CLI input. Pipe safe defaults for routine prompts. Kill stuck terminals and re-run with piped input.

## Steps

1. **Discover CLI options**
   Run `uvx skene analyze --help` to see available flags. Use only flags that appear in the output.

2. **Verify configuration**
   `ls .skene.config 2>/dev/null` — if missing: "Run `/skene-init` first." Stop.

3. **Run analysis**
   Default to project root. Choose appropriate flags based on --help output.
   ```
   uvx skene analyze .
   ```
   Tell the user: "Running analysis, this may take a few minutes."

4. **Handle result**
   - **Success**: Read results from `.skene/analysis/`, `skene-context/`, or legacy `skene/` and present them. Suggest `/skene-plan`.
   - **Failure**: Report the exact error, suggest a fix, **stop**. Do NOT generate your own analysis.

## Error handling

- **429 / quota**: "LLM provider quota error. Check billing, then re-run."
- **Permission errors**: Give user the command to run in their own terminal.
- **Timeout**: "Try a smaller directory."
- **Any other error**: Report verbatim.

## Output

Success: CLI results + "Run `/skene-plan` next."
Failure: Error + fix suggestion. No substitute analysis.
