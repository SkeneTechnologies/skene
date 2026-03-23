---
name: deploy-telemetry
description: Set up analytics and tracking infrastructure for growth loops. Use when the user says "deploy telemetry", "set up analytics", "tracking", "events", "push to supabase", or "skene push".
---

# Deploy Telemetry

Set up analytics infrastructure via the Skene CLI.

## Agent behavior rules

- **Autonomous.** Run CLI commands, report results, suggest next step. No mid-flow questions except for genuine blockers.
- **CLI is the source of truth.** Do NOT fabricate migration schemas or client code if the CLI fails.
- **User cannot type into agent terminals.** Pipe safe defaults for routine prompts. Kill stuck terminals.
- **Migrations are a genuine blocker.** Ask the user in chat to confirm before running `uvx skene push` — it writes migration files.

## Steps

1. **Discover CLI options**
   Run `uvx skene push --help` to see available flags. Use only flags that appear in the output.

2. **Verify prerequisites**
   `ls skene-context/growth-loops/ 2>/dev/null` — if missing: "Run `/skene-plan` first." Stop.
   `ls supabase/ 2>/dev/null` — if missing: "No Supabase directory. Set up Supabase first."

3. **Ask user to confirm**
   Tell the user: "`uvx skene push` will generate a Supabase migration with telemetry triggers. Apply now?"
   Wait for confirmation.

4. **Run push**
   After user confirms, run `uvx skene push` with appropriate flags from --help output.
   Report what migration file was created and where.

5. **Report result**
   Migration file path, what it contains, next step: "Run `/skene-status` to verify."

6. **Privacy reminder** (one line)
   "Remember GDPR/CCPA consent management before production tracking."

## Error handling

- **CLI failure**: Report error, suggest fix.
- **Permission errors**: Give user the command for their terminal.

## Output

Migration generated (or error), file path, next step (`/skene-status`).
