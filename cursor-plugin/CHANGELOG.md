# Changelog

## Unreleased

### Changed
- Docs and commands aligned with CLI: `skene build` writes `*_skene_triggers.sql`; `skene push` uploads artifacts (does not generate SQL). `skene status` Detail line shows latest matching migration plus `(+N)` for extra files.

## [0.1.0] - 2026-03-16

### Added
- Initial release
- 6 core skills: initialize-config, analyze-codebase, plan-growth-loop, build-implementation, deploy-telemetry, validate-loop
- 6 slash commands: /skene-init, /skene-analyze, /skene-plan, /skene-build, /skene-status, /skene-deploy
- PLG best practices rule (always-on)
- Auto-validation hooks for file edits and shell commands
- Local install/uninstall scripts for development
