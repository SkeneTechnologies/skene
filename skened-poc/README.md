# skened — Skene daemon (POC)

Background daemon that analyzes local git branches and emits **user journey maps**
(`Journey` schema). It runs as a localhost service with a `skene` **CLI**, a **REST API**,
and a simple web **dashboard**.

What it does:
- register git **projects** and list their **branches**
- run **async per-branch analysis** in **isolated git worktrees** (your working checkout is
  never touched)
- generate journeys with a pipeline that mirrors the reference `analyze-journey` command —
  **extract → merge → classify into the 7 canonical stages → assemble a validated `Journey`**
  (with the 4-layer swimlane model); **offline heuristics by default, or an LLM backend (LiteLLM)**
- analyze the **default branch from scratch** and **branch every other branch off it**,
  editing only what the code diff changes
- manage a **gold standard** (build from code, insert/edit, delete)
- compare journeys: **gap** (branch vs gold) and **drift** (branch vs branch)
- view it all in a web **dashboard** over the REST API (the same UI a future Tauri window
  would wrap)

## Quick start

```bash
uv sync
uv run pytest

# start the daemon (detached), check it, register a repo, watch analysis
uv run skene up --detach
uv run skene status
uv run skene project add /path/to/a/git/repo
uv run skene project ls
uv run skene analyze <project-id> --all
uv run skene runs <project-id>

# gold standard + comparisons
uv run skene gold from-branch <project-id>        # build gold from the default branch
uv run skene gap   <project-id> <branch>          # branch vs gold
uv run skene drift <project-id> <base> <head>     # branch vs branch
uv run skene config                               # show the active analysis backend

uv run skene down
```

### Commands

`up` / `down` / `status` / `config` · `project add|ls|rm` · `analyze` · `runs` ·
`gold show|set|from-branch|rm` · `gap` · `drift`. Run `uv run skene --help` (or `… <cmd> --help`)
for details.

### Dashboard

The daemon serves a simple web dashboard at its base URL (default
**http://127.0.0.1:8787**) — open it in a browser after `skene up`. It's a single
self-contained page (vanilla JS over the REST API) for managing projects, triggering
analysis, watching branch/run status, viewing journeys, building the gold standard, and
running gap/drift comparisons. A **⚙ Settings** panel configures the working-branch monitor
and the LLM provider/model/key at runtime (see *Settings*). It is the same web UI a future
Tauri window would wrap.

Branches are ordered **current → default → most-recent commit first** (`list_branches` sorts
server-side; `BranchInfo` carries `last_commit_at`/`is_default`/`is_current`). The table shows
the first 6 with a **"View N more branches"** toggle.

State lives under `~/.skene/` (`skene.db`, `worktrees/`, `journeys/`, `gold/`, logs).

## Gold standard

A per-project reference journey, used as the target for gap analysis. Build it from code,
insert/edit it by hand, or remove it:

- **build from a branch** (full from-scratch analysis): `skene gold from-branch <project> [--branch B]`
  · `POST /projects/{id}/gold/from-branch`
- **show**: `skene gold show <project> [-o file.json]` · `GET /projects/{id}/gold`
- **insert/edit** (full replacement from a Journey JSON file): `skene gold set <project> <file.json>`
  · `PUT /projects/{id}/gold`
- **remove**: `skene gold rm <project>` · `DELETE /projects/{id}/gold`

## Comparison: gap & drift

One engine (`comparison.py`, `compare_journeys`) powers both. Milestones are aligned across
two journeys (by id → fuzzy name → evidence-path overlap) and classified as
`matched` / `changed` (stage or evidence moved) / `missing` / `added`, with per-stage counts
and a coverage score.

- **Gap** — branch vs the gold standard: `skene gap <project> <branch>` ·
  `GET /projects/{id}/branches/{branch}/gap`
- **Drift** — branch vs branch: `skene drift <project> <base> <head>` ·
  `GET /projects/{id}/drift?base=<x>&head=<y>`

Computed on demand from the stored journeys (no extra runs). 404 if the gold standard or a
branch's analysis is missing.

## Architecture

```
Browser ─────HTTP──┐   GET /  → web dashboard (src/skened/web/index.html)
CLI (skene) ──HTTP─┴─> FastAPI (api.py) ──> DaemonService (service.py)
                                              ├─ ProjectRegistry (registry.py)      ┐
                                              ├─ GitService (git_service.py)        │
                                              ├─ JobQueue + workers (jobs.py)       │
                                              ├─ JourneyPipeline (journey_pipeline) ├─> ~/.skene
                                              ├─ comparison.py (gap / drift)        │   (sqlite, worktrees,
                                              └─ Storage (storage.py)               ┘    journeys, gold)
```

The CLI and dashboard are both thin clients over the same REST API; the daemon is the
single source of truth.

## Analysis pipeline (`skened.journey_pipeline`)

Mirrors the reference `analyze-journey` shape:

```
extract candidates ──> merge/dedup ──> classify into stages ──> assemble validated Journey
  (code agent)         (deterministic)   (per-milestone)          (+ 4-layer swimlane)
```

- **stages.py** — the 7 canonical stages (discovery → virality) + the 4-layer model.
- **extract.py** — `CandidateExtractor` seam. Default `HeuristicCodeScanner` walks the repo
  and applies regex/keyword signals matching the code agent's priorities (signup/auth,
  analytics events, email/queue/cron, billing/webhooks, referral/invite, POST routes).
- **classify.py** — `Classifier` seam. Default `HeuristicClassifier` (ordered keyword rules
  in the reference priority order). `LlmClassifier` is the faithful per-milestone LLM port.
- **merge.py / assemble.py** — deterministic, ported verbatim from the reference.

### Analysis bases (full, from-default, incremental)

A journey is rarely rebuilt from scratch — it's **derived from a base journey plus a code
diff**. `DaemonService._analyze_branch` picks the base:

- **First analysis of the default branch → full pipeline (from scratch).** This is the root
  base. (Gold-from-code is also always a full from-scratch analysis — a reference target,
  never a diff.)
- **First analysis of any other branch → branched from the default branch's journey**, diffing
  `default_base_commit..branch_commit`.
- **A branch that already has a journey, with a new commit → incremental**: branched from the
  **branch's own previous journey**, diffing only `prev_commit..new_commit`. This applies to
  every branch, including the default — once analyzed, new commits update its journey in place.

The branch-from step itself (used by all three bases):
  1. `git diff <base_commit>..<commit>` → changed / removed files.
  2. Base milestones whose evidence doesn't touch those files are **kept verbatim**.
  3. Changed/added files are **re-analyzed**; their fresh milestones replace/augment the base.
  4. Milestones whose only evidence was a removed file **drop out**.

  With no journey-relevant change, the result equals the base. This lives in
  `JourneyPipeline.branch_from()` (orchestrated by `DaemonService._branch_from_base()`).
  Steps 1–4 are the heuristic backend; with the LLM backend, `branch_from` instead hands the
  base journey + diff to `LlmBrancher` — see *Branch analysis with an LLM* below.

Re-analysis is keyed on the commit SHA: an unchanged HEAD is skipped (use `--force`); a new
commit triggers the incremental update.

### Working-branch monitor

The daemon watches each project's **checked-out HEAD** and auto-enqueues analysis when it
changes — a **branch switch** or a **new commit** on the current branch. It polls every few
seconds (`monitor.py`, `WorkingBranchMonitor`) and reuses `enqueue_analysis`, so a branch
already analyzed at its current commit is skipped. So just `git checkout <branch>` and the
journey for that branch appears without any manual command.

Config: `SKENE_MONITOR_ENABLED` (default `true`), `SKENE_MONITOR_INTERVAL` seconds
(default `3.0`), `SKENE_MONITOR_ON_COMMIT` (default `true`; set `false` to fire only on a
branch *switch*, not on new commits). All three are also editable live from the dashboard
**⚙ Settings** panel — no restart. `skene config` / `GET /health` report the current state.
With the LLM backend active a checkout/commit can spend tokens — turn the monitor off (or to
switch-only) to limit that.

## Settings

Editable at runtime via the dashboard **⚙ Settings** panel or `PATCH /settings` (read with
`GET /settings`): the monitor knobs above, plus the **analysis backend** and **LLM
provider/model/key** (`analysis_backend`, `llm_model`, `llm_api_key`, `llm_base_url`,
`llm_temperature`). Changing an LLM field rebuilds the pipeline immediately; `backend=llm`
with no model is rejected (400). The API key is **never returned** by the API (only an
`llm_api_key_set` flag).

Changes **persist** to `~/.skene/settings.json` (written `0600`, since it may hold the key)
and are re-applied on restart, overriding env for the fields you set in the UI. Env/`.env`
still supplies anything you haven't changed there.

### LLM backend (LiteLLM)

The pipeline runs offline (heuristics) by default and switches to an LLM backend when
configured — `factory.build_pipeline(settings)` picks based on `analysis_backend`/`llm_model`:

| Step | Heuristic (default) | LLM backend |
|---|---|---|
| extract candidates | `HeuristicCodeScanner` | `LlmCodeAgent` — agentic code-walk with fs-tools (`list_directory`/`read_file`/`search_files`/`emit_milestone`), as in skene/skene |
| classify into stages | `HeuristicClassifier` | `LlmClassifier` — per-milestone LLM call |
| branch from default | deterministic diff | `LlmBrancher` — see below |

One `LiteLLMClient` works across OpenAI / Anthropic / Gemini / local models by model string.

```bash
uv sync --extra llm
export SKENE_LLM_MODEL=anthropic/claude-sonnet-4-6     # turns on the LLM backend (auto)
export ANTHROPIC_API_KEY=...                           # or SKENE_LLM_API_KEY=...
skene down && skene up --detach
skene config                                           # shows the active backend
```

Config (env, `SKENE_` prefix, or a `.env` file): `SKENE_ANALYSIS_BACKEND` (`auto`/`heuristic`/`llm`),
`SKENE_LLM_MODEL`, `SKENE_LLM_API_KEY`, `SKENE_LLM_BASE_URL`, `SKENE_LLM_TEMPERATURE`,
`SKENE_LLM_MAX_TURNS`, `SKENE_LLM_CLASSIFY_CONCURRENCY`.

**LLM errors fail the run** — they are never silently degraded. Any failure in an LLM step
(transport, auth, rate-limit, or unusable model output) raises `LlmAnalysisError`: a queued
analysis run is recorded as `failed` with the error (visible via `skene runs <project>`),
and a synchronous call like gold-from-branch returns HTTP 502 with the message. The
heuristic backend is a *configuration choice* (`analysis_backend=heuristic` or no model),
not an automatic fallback.

### Branch analysis with an LLM (the branched-from-default model)

When the LLM backend is on, a non-default branch's journey is produced by `LlmBrancher`:
it is shown the **base journey** (the default branch's analysis) plus the **code diff**, and
returns structured **edits** (add / update / remove milestones). The edits are applied to the
base deterministically and re-assembled, so the result is always a schema-valid `Journey`
regardless of model output. Empty edits → the branch journey equals the base. If the LLM call
itself fails, the run fails (no deterministic fallback when the LLM backend is active).

## Status & what's next

**Built:** project management · async worktree analysis · journey pipeline (heuristic + LLM
via LiteLLM) · default-from-scratch + branch-from-default + incremental updates ·
working-branch monitor (auto-analyze on switch/commit) · gold standard CRUD ·
gap & drift comparison · web dashboard · fail-loud LLM runs.

**Not yet built** (seams in place): **pull-from-GitHub** (`git fetch`/`pull` wrappers exist in
`git_service.py`) · an optional LLM **"explain the gap/drift"** narration · packaging the
dashboard into a **Tauri** desktop window.

## Tech

Python ≥3.11, `uv`-managed. FastAPI + uvicorn (daemon/API), Typer (CLI), Pydantic v2
(models/validation), stdlib `sqlite3` (state), `git` via subprocess (worktrees). LiteLLM is
an optional extra (`uv sync --extra llm`) for the LLM backend. Tests: `uv run pytest`.
