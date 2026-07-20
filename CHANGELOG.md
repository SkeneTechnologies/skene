# Changelog

The skene CLI (Python) and TUI (Go) are released and tagged independently,
but TUI version `X.Y.Z` is always pinned to CLI version `X.Y.Z`. The
**Combined** section below is the one to share with TUI users — it bundles
both sides of a release into a single set of notes. The per-component
sections after it have the full detail.

CLI releases are tagged `vX.Y.Z`; TUI releases are tagged `tui-vX.Y.Z`.

## Combined releases

### [0.4.1] - 2026-05-20

Pairs **CLI `v0.4.1`** with **TUI `tui-v0.4.1`**. The CLI side is a pure
version bump to stay in lockstep with the TUI; all user-facing changes are
in the TUI and its installer.

#### Added
- **Anonymous, opt-out telemetry.** The TUI now sends anonymous usage events
  (no PII; anon ID is a hash of hostname) to help us prioritize improvements.
  Events cover the full lifecycle — startup/exit, view transitions,
  provider/model/project selection, analysis/plan/build/validate/deployment
  outcomes (with durations), auth flow, and errors.
- **Telemetry toggle on the welcome screen.** Press `t` to flip telemetry
  on/off. The welcome screen shows the current state; the setting persists
  per-machine.

#### Fixed
- **Re-entering the welcome flow no longer leaves stale screens.** After
  abandoning a Reconfigure flow and pressing Enter at welcome, the TUI now
  reloads config and clears previously-selected provider/model and the
  API-key, model, local-model, and auth views.
- **Cancelled analyses are now reported as cancelled, not failed.** Ctrl-C
  during an analysis is distinguished from a real failure in the UI and in
  telemetry (`analysis_cancelled` vs `analysis_failed`).

#### Changed — installer (`tui/install.sh`)
- SHA-256 checksum verification of the downloaded binary against the
  release's `checksums.txt`.
- Only `tui-v*` releases are considered (CLI and skills tags are skipped).
- HTTPS downloads enforce `--proto '=https' --tlsv1.2`.
- Default install path is sudo-free: `SKENE_INSTALL_DIR` →
  writable `/usr/local/bin` → `$HOME/.local/bin`; sudo only as last resort.
- Existing macOS code signatures are preserved (ad-hoc signing only when
  unsigned).
- Verify step warns if another `skene` earlier on `PATH` shadows the new
  install and prints an `export PATH=…` hint.
- Temp directory is cleaned up on exit, interrupt, or error.
- New env var `SKENE_VERSION` (accepts `0.4.0`, `v0.4.0`, or `tui-v0.4.0`).
  The legacy `VERSION` env var still works but is deprecated.

#### Breaking changes
- None. Installer's `VERSION` env var is deprecated (warn-only) in favor of
  `SKENE_VERSION`.

## skene CLI

### [Unreleased]

#### Changed
- **Stages are no longer force-filled.** The synthesis step is told which evidence sources were analysed and instructed to populate a stage only when the evidence genuinely shows that lifecycle step — an app-only analysis now leaves e.g. discovery empty instead of promoting the in-app signup flow into it. Accordingly, the canonical stage definitions moved signup/account-creation from discovery (now acquisition surfaces only: landing/pricing pages, campaign attribution) into onboarding (now "begins with account creation"). The per-feature classify fallback carries the same coverage rule.
- **`analyse-journey` restructured around a feature map.** The code/schema subagents now emit product *features* (capabilities with evidence) instead of candidate milestones — same shape, honest name — and the merged, deduplicated feature map is written as a `features.yaml` artifact next to `journey.yaml`. A new synthesis step (one LLM call over the whole feature map) composes actual user-journey milestones from groups of related features, named from the user's perspective and stage-assigned with global context; milestone evidence is the union of its features' evidence. The per-feature classifier remains as the fallback when synthesis fails (every feature becomes its own milestone — the old behavior). Wire/API renames: part type `milestone` → `feature` (`MilestonePart`/`CandidateMilestone` → `FeaturePart`/`Feature` in the OpenAPI schema), subagent tool `emit_milestone` → `emit_feature`, task summaries report `featuresEmitted`, and the main agent's finalize tool is now `synthesize_journey`. The `journey.yaml` schema itself is unchanged. Old dev session DBs with `milestone` parts will 500 on read (pre-1.0 posture); delete the DB file if it bites.

#### Removed
- **Legacy pipeline commands removed: `analyze`, `plan`, `build`, `validate`.** The journey flow (`analyse-journey`) is now the sole analysis entry point. Removed alongside them:
  - The legacy analyzers (`TechStackAnalyzer`, `GrowthFeaturesAnalyzer`, `ManifestAnalyzer`, `DocsAnalyzer`), the strategy framework (`skene.strategies`), the planner (`skene.planner`), docs generation (`skene.docs`), templates (`skene.templates`), objectives (`skene.objectives`), and the manifest schemas (`skene.manifest`).
  - Dead support code with no remaining callers: the engine delta generator (`skene.engine.generator`), growth-loop JSON generation (`skene.growth_loops.storage`), and the AST-based loop validator (`skene.validators.loop_validator`, `ts_parser`, `py_parser`).
  - The `benchmarks/` suite (it benchmarked the removed pipeline), the cursor-plugin `skene-analyze`/`skene-plan`/`skene-build` commands and their skills, and the corresponding docs pages.
  - `skene/__init__.py` now exports only `CodebaseExplorer`, `build_directory_tree`, `DEFAULT_EXCLUDE_FOLDERS`, `Config`, `load_config`, `LLMClient`, `create_llm_client`.
- Kept: `analyse-journey`, `status` (engine.yaml validation), `push`, `config`, `login`/`logout`, `features`, `serve`, `attach`.

### [0.4.1] - 2026-05-20

Maintenance release — version bump only.

- `__version__` and `pyproject.toml` bumped from `0.4.0` to `0.4.1`. No behavior, API, dependency, or test changes in `src/` or `test/`.
- Companion release: TUI `tui-v0.4.1` (anonymous telemetry, installer hardening, config-reload fix).

## skene TUI

### [Unreleased]

#### Changed
- **Journey analysis streams `feature` parts.** Regenerated the API client for the CLI's feature-map restructure (`MilestonePart` → `FeaturePart`); the run log now shows `✦ feature: <name>` lines and a features-collected count. Requires a CLI with the matching wire shape.

### [tui-0.4.1] - 2026-05-20

#### Added
- **Anonymous, opt-out telemetry.** A new background telemetry client (`internal/services/telemetry`) sends anonymous usage events to a Supabase Edge Function proxy. Events are non-blocking (queue size 64, 5s HTTP timeout, drained on exit with a 2s grace period) and never include PII — the "distinct ID" is an FNV hash of the hostname (`anon-<hex>`). Every event carries `app_version`, `os`, `arch`, `session_id`, and a monotonic `event_seq`.
  - Tracked events cover the full TUI lifecycle: `tui_opened` / `tui_exited`, `view_entered`, provider/model/project-dir selection, `analysis_started/completed/failed/cancelled/retried`, `plan_*`, `build_*`, `validate_*`, `deployment_*`, `next_step_triggered/cancelled`, `auth_succeeded` / `auth_fallback_used`, `visualizer_opened`, `output_dir_opened`, `existing_analysis_action`, `config_reused` / `config_reconfigured`, `telemetry_toggled`, and an `error` event with `error_code`. Completion events include durations.
  - Forks and local builds (no injected credentials) silently drop events. Dev/staging can override via `SKENE_TELEMETRY_URL` / `SKENE_TELEMETRY_KEY`.
- **Telemetry toggle on the welcome screen.** Press `t` to flip telemetry on/off. The welcome screen now shows `Telemetry: on/off • Anonymous usage stats help us improve Skene`. The setting is persisted per-machine in user config (`telemetry = "true"|"false"`), and a `telemetry_toggled` event is sent even when opting out (just before the client is disabled).

#### Fixed
- **Re-entering the welcome flow no longer leaves stale screens.** After abandoning a Reconfigure flow and pressing Enter at welcome, the app now calls a new `Manager.ReloadConfig()` and clears the selected provider/model, API-key view, model view, local-model view, and auth view, so navigation behaves consistently.
- **Cancelled analyses are now reported as cancelled, not failed.** `runUVX` in the growth engine checks `ctx.Err()` after the process exits and returns the cancellation error rather than the generic broken-pipe / killed exit. This is also what makes `analysis_cancelled` distinct from `analysis_failed` in telemetry.

#### Changed — installer hardening (`tui/install.sh`)
- **Checksum verification.** Releases now ship a `checksums.txt`; the installer verifies the downloaded binary's SHA-256 (via `sha256sum` or `shasum`) and aborts on mismatch. Older releases without a checksums file produce a warning and proceed.
- **Correct release-tag scoping.** Only `tui-v*` releases are considered, skipping the Python CLI (`v*`) and skills (`skills-v*`) tags.
- **Safer HTTPS.** All downloads go through a `curl_get` wrapper enforcing `--proto '=https' --tlsv1.2 -fsSL`.
- **No-sudo install path by default.** Install location resolves to `SKENE_INSTALL_DIR` → writable `/usr/local/bin` → `$HOME/.local/bin`, with sudo only as a last resort.
- **macOS code-signing preserved.** The installer only applies an ad-hoc signature when the binary isn't already signed.
- **PATH sanity check.** Verify step warns if a different `skene` shadows the new install and prints an `export PATH=…` hint.
- **Cleanup on exit.** Temp directory is removed via `trap cleanup EXIT INT TERM`.
- **New env var `SKENE_VERSION`** (accepts `0.4.0`, `v0.4.0`, or `tui-v0.4.0`). The legacy `VERSION` still works but is deprecated.

#### Internal
- `tui/Makefile` `VERSION=tui-v0.4.1`; `GrowthPackageVersion` pinned to skene CLI `0.4.1`.
- `Config` gains a `TelemetryEnabled bool`; `LoadConfig` distinguishes "absent" (default on) from explicit `false`.

#### Breaking changes
- None. `install.sh`'s `VERSION` env var is deprecated (warn-only) in favor of `SKENE_VERSION`.
