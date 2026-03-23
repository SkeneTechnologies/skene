# Contributing to Skene

## Repository Structure

This is a monorepo with two packages:

| Package | Directory | Language |
|---------|-----------|----------|
| CLI | `src/skene/` | Python |
| TUI | `tui/` | Go |

## Development

### CLI (Python)

```bash
uv sync                          # Install dependencies
uv run ruff check .              # Lint
uv run ruff format --check .     # Check formatting
uv run pytest tests/             # Run tests
uv run skene --help              # Run the CLI
```

### TUI (Go)

```bash
cd tui
make install                     # Install Go dependencies
make build                       # Build the binary
make test                        # Run tests
make lint                        # Lint (requires golangci-lint)
make fmt                         # Format code
make run                         # Run the TUI
```

See `make help` for the full list of targets.

## Conventions

### CLI

- **Output:** All terminal output goes through `skene.output` — never use `print()`, `Console()`, or stdlib `logging`. See the module docstring in `src/skene/output.py` for details.
- **Style:** Ruff handles linting and formatting (config in `pyproject.toml`).
- **Tests:** Add or update tests for any behavioral change.

### TUI

- **Style:** `gofmt` for formatting, `golangci-lint` for linting.
- **Tests:** Add or update tests for any behavioral change.

## Documentation

Keep docs up to date with your changes. If a PR changes behavior, CLI flags, configuration, or public APIs, update the relevant documentation in the same PR — don't leave it for a follow-up.

## Pull Requests

- Branch from `main`
- Keep PRs focused on a single change — don't mix new features with refactoring, renames, or unrelated cleanup
- Run checks before submitting: `uv run ruff check . && uv run ruff format --check . && uv run pytest tests/` for CLI changes, `cd tui && make lint && make test` for TUI changes
- Update any documentation affected by your changes
- Include a test plan in the PR description

## AI-Generated Code

We welcome the use of AI coding tools, but the author is responsible for every line in the PR. If you use AI assistance:

- **Keep PRs small and reviewable.** LLMs tend to produce large diffs. Break the work into focused PRs rather than submitting everything at once.
- **Read every line and challenge the AI's choices.** Don't accept suggestions uncritically — question naming, structure, error handling, and whether the code is actually needed.
- **Stay focused.** Resist the AI's tendency to "improve" surrounding code. If the task is a bug fix, the PR should contain a bug fix — not a bug fix plus a refactor plus new type annotations.
- **Prefer libraries over hand-rolled solutions.** If a well-maintained package solves the problem, add it as a dependency rather than writing fragile custom code. Use judgement — evaluate the dependency's size, maintenance status, and transitive footprint before pulling it in.
- **Self-review from a clean context.** Before opening the PR, ask an AI tool (fresh conversation, no prior context) to find issues in the code affected by your changes. It will always flag something — that's the point. Evaluate each finding and fix the real ones; false positives are cheap, missed bugs are not.
- **Own the PR after opening it.** Don't open and walk away. Check the PR on GitHub: make sure there are no merge conflicts, CI passes, and review comments are addressed. The PR is your responsibility until it's merged.
