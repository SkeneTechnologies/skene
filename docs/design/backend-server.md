# Skene Backend Server — Design

Status: in progress (2026-07-06) — phases 1-4 implemented, phase 5 pending.
Work lands on feature branches targeting the `v1.0` integration branch.

| Phase | Status | Where |
|---|---|---|
| 1. Schema + streaming loop | **done** | `feat/server-phase1` |
| 2. Server MVP | **done** | `feat/server-phase2` |
| 3. Agentic flow | **done** | `feat/server-phase3` |
| 4. TUI cutover | **done** | `feat/server-phase4` |
| 5. Hardening & growth | pending | |

Goal: turn skene into a client/server system where a **main skene agent** orchestrates
**code/db subagents** (and future ones), and CLI + TUI are thin clients of a single
backend service. Architecture is modeled on opencode
(`/Users/miche/skene/projects/opencode`), adapted to skene's Python engine.

---

## 1. Core decision: copy opencode's architecture, not its code

opencode's current codebase is a TypeScript/Bun monorepo built on the Effect runtime,
with event-sourced SQLite persistence. Skene's entire engine — agents, `agent_loop`,
toolsets, tree-sitter/sqlglot analyzers, psycopg introspection, the LLM provider
layer — is pure async Python and already cleanly separated from the CLI.

**Recommendation:** build the server in Python (FastAPI) around the existing engine,
and port opencode's *design*: the API shape, the session/message/part model, the SSE
event bus, the task-tool subagent pattern, the schema-first → OpenAPI → generated
client flow, and the permission-ask flow.

Why not reuse opencode's code directly:

- Its `core` package is inseparable from the Effect runtime and its custom `LayerNode`
  DI graph — adopting it means adopting Effect wholesale and rewriting skene's
  analyzers in TypeScript (tree-sitter, sqlglot, psycopg all have TS analogues, but
  it's a full engine port for zero product gain).
- What makes opencode valuable to us is transferable without the runtime: wire shapes
  (`packages/schema/src/session-message.ts`), route surface
  (`packages/opencode/src/server/routes/instance/httpapi/groups/session.ts`), the task
  tool (`packages/opencode/src/tool/task.ts`), the SSE event handler
  (`.../handlers/event.ts`), and the SDK generation pipeline
  (`packages/sdk/js/script/build.ts`).

The escape hatch stays open: if skene later converges on opencode's product shape
(general coding agent, plugins, MCP, 25 providers), the API contract designed here is
close enough to opencode's that a TS rewrite could slot in under the same clients.

### What we take vs. skip

| opencode piece | Verdict | Notes |
|---|---|---|
| Schema-first contract → OpenAPI → generated clients | **Take** | FastAPI gives OpenAPI natively; `oapi-codegen` for the Go TUI client |
| Sessions/messages/tagged-union parts with streaming `ToolState` | **Take** | Copy shapes from `packages/schema/src/session-message.ts` |
| SSE `/event` bus with heartbeat + directory filtering | **Take** | Copy semantics from `handlers/event.ts` |
| Subagents = child sessions spawned by a `task` tool | **Take** | This *is* requirement #1 |
| Permission `ask` flow (tool pauses, client answers via HTTP) | **Take** (phase 5) | Needed for db-write tools later |
| Per-request workspace routing (`x-opencode-directory` header) | **Take** | One server, many projects |
| `serve` / `run` / `attach` CLI lifecycle | **Take** | Same three verbs |
| SQLite persistence | **Take, simplified** | Plain relational state + event feed, not full event sourcing |
| Event-sourced projectors, optimistic concurrency | **Skip for now** | Most complex piece; revisit if we need multi-writer/sync |
| Effect runtime, `LayerNode` DI | **Skip** | Plain Python DI (constructor injection / FastAPI deps) |
| mDNS discovery, PTY websocket, plugin system, MCP | **Later** | Not needed for v1 |
| ai-sdk provider layer | **Skip** | skene's `llm/` already covers this in Python |

---

## 2. Target layout

```
src/skene/
  schema/        # NEW: pydantic wire models — single source of truth
                 #   session.py, message.py (parts, ToolState), event.py,
                 #   agent.py, permission.py
  core/          # NEW: domain services (no HTTP)
                 #   bus.py          in-process pub/sub, typed events
                 #   store.py        SQLite (aiosqlite) sessions/messages/parts
                 #   sessions.py     create/prompt/abort/fork, run coordinator
                 #   agents.py       agent registry (primary vs subagent)
                 #   tasks.py        the task tool: spawn child sessions
                 #   permissions.py  ask/allow/deny rulesets  (phase 2)
                 #   workspace.py    per-directory context cache
  server/        # NEW: FastAPI app
                 #   app.py, routes/{session,event,agent,config,provider,file}.py
                 #   sse.py, auth.py
  llm/           # existing — unchanged (providers, factory)
  analyzers/     # existing engine; journey steps become tools/subagents
  cli/           # thin client: serve, run, analyse-journey (spawns embedded server)
tui/             # Go — generated client + SSE reader replaces uvx stdout-scraping
```

The `schema` package mirrors opencode's `@opencode-ai/schema`: everything on the wire
is defined once in pydantic, FastAPI derives OpenAPI from it, and both the Go TUI
client and a future TS/web client are generated from that spec.

---

## 3. Domain model

Copied from `packages/schema/src/session-message.ts`, trimmed to what skene renders.

```
Project   { id, directory, name }
Session   { id, projectID, parentID?, agent, title, status: idle|running|error,
            created, updated }
Message   { id, sessionID, role: user|assistant|synthetic, created,
            # assistant only:
            agent, model, tokens, cost, finish }
Part      { id, messageID, type: text | reasoning | tool | milestone | artifact }
ToolPart  { tool, callID, state: pending → running → completed | error,
            input, output, title, metadata }
```

Two skene-specific part types:

- **`milestone`** — a `CandidateMilestone` emitted by `emit_milestone`. Today these go
  into an in-memory collector list; as parts they persist, stream to the UI live
  ("found: user signs up → auth/signup.ts"), and remain queryable per session.
- **`artifact`** — a produced file (`journey.yaml`), with path + summary, so clients
  can offer "open visualizer" without knowing engine internals.

**Persistence:** single global SQLite DB at `~/.local/share/skene/skene.db`
(WAL mode, `aiosqlite`), tables ≈ the model above plus `permission_request`. Write
state directly and publish an event on every mutation — skip opencode's
event-sourcing/projector layer (`packages/core/src/event.ts`) until there's a
multi-writer or sync requirement. Artifacts still land in the workspace
(`skene-context/journey.yaml`) as today.

**Events** (SSE wire shape `{id, type, properties}`, exactly like opencode):

```
server.connected, server.heartbeat (10s)
session.created | updated | idle | error
message.created | updated
part.created | updated          # streaming text + tool-state transitions
permission.asked | answered
```

---

## 4. API surface

All routes scoped by workspace via `x-skene-directory` header (fallback: server cwd),
mirroring opencode's `workspace-routing.ts`. Auth: bearer token from `.skene.config`;
bind 127.0.0.1 by default, token required for non-local binds.

```
GET  /event                                  SSE stream (filtered by directory)

POST /session                                create {agent?, parentID?, title?}
GET  /session                                list
GET  /session/{id}                           get
GET  /session/{id}/children                  subagent sessions
GET  /session/{id}/message                   messages + parts
POST /session/{id}/message                   prompt: returns user Message immediately,
                                             run proceeds async, progress via /event
POST /session/{id}/abort                     cancel the running task tree
POST /session/{id}/permissions/{permID}      answer an ask (phase 2)

GET  /agent                                  registry (primary + subagents)
GET  /provider                               available providers/models
GET  /config          PATCH /config          resolved config (secrets redacted)

POST /journey/analyse                        v1-compat convenience: creates a session,
                                             sends the canned analyse prompt, returns
                                             {sessionID}; result = artifact part
GET  /journey                                latest journey.yaml as JSON (replaces the
                                             TUI visualizer's file read)

GET  /health   GET /doc (openapi.json)
```

Client generation: CI job runs the server's `openapi.json` through `oapi-codegen`
(Go, for `tui/`) — same pattern as opencode's `packages/sdk/js/script/build.ts`. SSE
consumption is a small hand-written reader on each client.

---

## 5. The agentic flow

Requirement #1 restated in opencode's vocabulary: **skene is a primary agent; code
and db are subagents invoked through a `task` tool; a subagent run is a child
session** (opencode: `tool/task.ts` + `sessions.create({parentID})`).

### Agent registry

```python
Agent(
  name="skene",  mode="primary",
  prompt=MAIN_AGENT_INSTRUCTIONS,
  tools=[task, introspect_db, finalize_journey, read_artifact],
)
Agent(name="code",   mode="subagent", prompt=CODE_AGENT_INSTRUCTIONS,   toolset=FsToolset)
Agent(name="schema", mode="subagent", prompt=SCHEMA_AGENT_INSTRUCTIONS, toolset=SchemaToolset)
# future: analytics, docs, api-surface, ...
```

The task tool advertises available subagents in its description (opencode's
`describeTask` pattern), so adding an agent to the registry makes it reachable
without touching the main agent's prompt.

### Keeping determinism where it earns its keep

Today `run_journey_pipeline` is fully deterministic orchestration: specialize ∥
schema-agent ∥ code-agent → merge → classify fan-out → assemble. Making the main
agent free-form would trade reproducibility for nothing. Split it:

- **Agentic:** *which* subagents to spawn, with what focus, whether to re-run one that
  under-delivered, how to react to a missing schema. The main agent calls
  `task(agent="code", prompt=...)` and `task(agent="schema", ...)` — in parallel via
  multiple tool calls in one turn.
- **Deterministic tools:** `introspect_db(db_url)` (thread-executor around the sync
  psycopg call), `finalize_journey()` (merge + classify fan-out + assemble +
  serialize — the current post-agent pipeline verbatim, exposed as one tool that
  reads milestone parts from child sessions).

`analyse-journey` then becomes a **canned prompt** to a fresh skene session (opencode's
"command" concept) — same UX, but every run is now inspectable as a session tree, and
"add an analytics agent" is a registry entry plus a prompt tweak.

### Engine refactor: the one real surgery

`agent_loop.run_agent()` (`src/skene/llm/agent_loop.py:171`) currently runs to
completion and returns a result — nothing streams. It must become event-emitting:

```python
async def run_agent(...) -> AsyncIterator[AgentEvent]:
    # yields: turn_started, text_delta, tool_call_started(callID, name, input),
    #         tool_call_finished(callID, output|error), turn_finished, run_finished
```

plus cooperative cancellation (checked between turns and passed into tool handlers).
The session **run coordinator** in `core/sessions.py` consumes this iterator,
persists parts, and publishes bus events — the loop itself stays free of HTTP and
storage concerns, as it is today. `LLMClient` and the providers don't change;
existing `Tool`/toolset classes are reused as-is, gaining an optional `context`
(sessionID, abort signal, `ask()` for permissions later).

Everything else in the engine is reused untouched: pipeline steps become tool
bodies, `FsToolset`/`SchemaToolset` become subagent toolsets, `llm/factory.py`
becomes the provider service.

---

## 6. Clients

**CLI** (`src/skene/cli/`):
- `skene serve [--port 4906] [--host]` — run the server headless.
- `skene analyse-journey ...` — unchanged UX: starts an embedded server (in-process
  lifespan, no socket needed — call `core` directly), creates a session, sends the
  canned prompt, renders `/event` progress with rich. This is opencode's `run`.
- `skene attach <url>` — later, once remote serving matters.

**TUI** (`tui/`): the entire `internal/services/growth/engine.go` uvx-spawn +
stdout-scraping + stall-timer machinery is deleted. The TUI either spawns
`skene serve` (owning the process) or connects to a running one, then drives the
generated Go client and renders the SSE stream. Wins: real structured progress
(per-agent, per-tool), reliable interactive prompts via the permission/question flow
instead of stdin heuristics, and the visualizer reads `GET /journey` instead of
parsing `journey.yaml` itself.

---

## 7. Cross-cutting watch-outs

- **Blocking introspection:** `postgres_live.introspect_db` is sync psycopg inside an
  async server — wrap in `asyncio.to_thread`. Same for any tree-sitter/sqlglot
  hot spots if they show up in traces.
- **Secrets:** `db_url` is deliberately never persisted today
  (`analyse_journey.py`, `_redact_db_url`). Preserve that: it may appear in a tool
  *input* on the wire → redact DSNs in persisted/streamed tool inputs. API keys are
  per-request/per-config, never in the DB, redacted in `GET /config`.
- **Concurrency isolation:** collectors are currently in-memory globals per run;
  milestone-as-part removes them, but audit the engine for any other module-level
  state before serving concurrent sessions.
- **Session cleanup:** abort must cancel the whole child-session tree (opencode
  does this through the parent abort signal).

---

## 8. Phased plan

1. **Schema + streaming loop.** Create `skene/schema` (session/message/part/event
   models); refactor `agent_loop.run_agent` into an event-yielding iterator with
   cancellation. Engine still runnable via the old CLI (adapter that drains the
   iterator). Smallest reviewable slice, unlocks everything.
2. **Server MVP.** `skene/core` (bus, store, sessions) + FastAPI app: session CRUD,
   prompt, abort, `/event` SSE, `/journey/analyse` compat route running the current
   deterministic pipeline inside a session. CLI `serve` command; `analyse-journey`
   switched to embedded-server mode.
3. **Agentic flow.** Agent registry, task tool, child sessions; recast code/schema
   agents as subagents and `analyse-journey` as the canned main-agent prompt;
   `finalize_journey` tool. Retire the standalone pipeline path once output parity
   is verified against golden `journey.yaml` fixtures.
4. **TUI cutover.** Generate the Go client, replace `growth/engine.go`, wire the
   visualizer to `GET /journey`. Delete stdout parsing.
5. **Hardening & growth.** Permission ask flow, `attach` + auth for remote serving,
   additional subagents, optional durable event log if sync/multi-client demands it.

Phases 1–3 keep `main` shippable throughout: the old code path stays until phase 3's
parity check passes.

### Phase 1 — as built (notes for phase 2+)

What exists after phase 1 (`feat/server-phase1`), and the contracts the next
phases build on:

- **`skene/schema`** is the wire-model package. Conventions baked in: camelCase
  JSON / snake_case Python (`WireModel` base in `schema/base.py` sets
  `alias_generator=to_camel`, `populate_by_name`, `serialize_by_alias`,
  `extra="forbid"` — new wire models must inherit from it); discriminated unions
  `Message` (by `role`), `Part` (by `type`), `ToolState` (by `status`), `Event`
  (by `type`); IDs from `schema/ids.py` `new_id(prefix)` — prefixed
  (`ses_/msg_/prt_/evt_/prj_`), time-sortable, monotonic **per process only**
  (don't rely on cross-process ordering; the store's `created` column is the
  cross-process truth).
- **Streaming loop**: `agent_loop.run_agent_stream()` yields `TurnStarted`,
  `AssistantText`, `ToolCallStarted`, `ToolCallFinished(error: bool)`, then
  always `RunFinished(result)`. `run_agent()` is a draining wrapper (the batch
  CLI path uses it unchanged). Reach it via `LLMClient.run_agent_stream(...)` so
  provider overrides keep working. Phase 2's run coordinator maps events →
  parts: `TurnStarted`+`AssistantText` → `TextPart`, `ToolCallStarted` →
  `ToolPart(state=running)`, `ToolCallFinished` → `completed`/`error` state.
  Note: providers return full turns, so there are no token-level text deltas
  yet — `PartUpdated.delta` is wired but per-turn granularity for now; true
  token streaming needs `generate_with_tools` streaming variants (later, not
  phase 2 scope).
- **Cancellation**: `abort: asyncio.Event`, checked before each LLM call and
  each tool dispatch. It does **not** interrupt an in-flight provider call —
  the phase-2 abort endpoint should set the event *and* cancel the session's
  asyncio task, and must fan out to child-session tasks (phase 3).
- **Aborted history caveat**: an aborted run's message list can end on an
  assistant message with unanswered tool calls. If a session is ever resumed
  from stored history, synthesize `tool` results for the dangling calls first —
  providers reject histories with unanswered tool calls.
- **Deliberate loose end**: `MilestonePart.milestone` is `dict[str, Any]`.
  Phase 3 moves `CandidateMilestone`/`Evidence` into `skene/schema` (analyzers
  re-export) and types it — do this when recasting the agents, not before.

### Phase 2 — as built (notes for phase 3+)

What exists after phase 2 (`feat/server-phase2`), and the contracts phase 3
builds on:

- **`skene/core`**: `bus.py` (in-process pub/sub; events publish with an
  optional `directory` — subscribers with a directory filter get matching +
  server-wide events), `store.py` (aiosqlite, WAL, one global DB; rows keep
  the full wire JSON in a `data` column plus query columns; `save_message`/
  `save_part` are upserts), `sessions.py` (`SessionService`), `journey.py`
  (the canned run), `services.py` (`create_services` wiring; `SKENE_DB_PATH`
  overrides the DB location), `embedded.py` (in-process entry for the CLI),
  `redact.py` (DSN redaction).
- **Run coordinator**: `SessionService.consume_stream(session, message,
  stream)` maps phase-1 stream events → parts exactly as specified and is
  the piece phase 3 reuses for subagent runs. It returns the final
  `AgentRunResult`; the *caller* owns session status transitions and the
  assistant message's finish/tokens bookkeeping (see `_chat_run` for the
  canonical sequence). `start_run` registers any coroutine as a session's
  abortable background task. Tool inputs and user text are DSN-redacted
  before persist (`core/redact.py`).
- **Child-session plumbing already exists**: `SessionService.create_session`
  takes `parent_id` (validated against the store), `SessionCreateRequest`
  carries `parentId`, and `GET /session/{id}/children` is live. Phase 3's
  task tool is: create a child session with `parent_id`, `start_run` a
  subagent run in it, wait, and surface the result to the parent.
- **One run per session** (`SessionBusyError` on concurrent prompt).
  Parallel subagents = one child session each; each `start_run` is an
  independent entry in `SessionService._runs`. Use `sessions.wait(id)` to
  join a run (that's how the embedded CLI and the tests do it).
- **Abort does NOT fan out yet**: child runs are independent asyncio tasks,
  so cancelling a parent's task does not cancel its children. `abort()`
  sets the cooperative event and cancels that one session's task. Phase 3
  must make the parent's abort walk the child-session tree (either the
  task tool holds child session ids and aborts them in its cancellation
  path, or `abort()` recurses over `store.list_children`).
- **`llm_factory` is one global factory** (provider/model resolved once at
  `skene serve` startup, or the CLI's client in embedded mode). Per-agent
  model overrides (`AgentInfo.model` is already on the wire) are a phase-3
  registry concern — thread them through the registry, not the factory.
- **Prompt runs are placeholder chat** (no tools, generic instructions in
  `sessions._CHAT_INSTRUCTIONS`). Phase 3 swaps in the agent registry +
  task tool here; everything else (parts, events, abort) stays.
- **Journey runs** (`POST /journey/analyse` and the CLI) wrap the untouched
  deterministic pipeline in a session with coarse parts: one
  `journey_pipeline` ToolPart (running → completed/error), then milestone /
  artifact / summary-text parts from the result. Live-DB introspection runs
  inside the run via `asyncio.to_thread`; `db_url` is never persisted.
  Phase 3 replaces this wrapper (`core/journey.py`) with the main-agent
  flow — parity check against golden `journey.yaml` fixtures before
  deleting it. Contract to preserve for clients: the route returns
  `{sessionId}` immediately, and a finished run has an `artifact` part
  pointing at `journey.yaml` plus `session.idle`/`session.error` on the bus.
  These sessions use `agent="journey"`; phase 3's canned-prompt sessions
  will be `agent="skene"` — nothing keys off the string yet, but the TUI
  shouldn't either.
- **MilestonePart shape mismatch to resolve in phase 3**: the phase-2
  wrapper emits *final* `Milestone` dumps (post-classification, with a
  `stage_id` key), because that's what the pipeline returns. Phase 3's
  live `emit_milestone` parts will be `CandidateMilestone`s (no stage yet)
  per the phase-1 loose-end note. When typing `MilestonePart.milestone`,
  pick the candidate shape and drop the phase-2 form with the wrapper —
  don't try to support both.
- **Server**: `skene.server.create_app(services=None, *, db_path,
  llm_factory, auth_token)` — pass prebuilt services (tests/embedded) or
  let the lifespan own them (`skene serve`). Routes as designed except
  `GET /agent`, `GET /provider`, `GET/PATCH /config` (deferred: registry is
  phase 3, config surface phase 5). Optional bearer auth; `skene serve`
  refuses non-local binds without a token. `/doc` returns openapi.json.
- **CLI**: `skene serve` (new), `skene analyse-journey` now runs through
  `core.embedded.run_journey_embedded` — same UX (pipeline `status()` lines
  still print), but every CLI run persists a session trace in the skene DB.
- **Testing note**: httpx's `ASGITransport` buffers whole responses, so SSE
  tests drive the generator directly or speak raw ASGI (see
  `tests/test_server/test_sse.py`).

### Phase 3 — as built (notes for phase 4+)

What exists after phase 3 (`feat/server-phase3`), and the contracts the
TUI cutover builds on:

- **Agent registry** (`core/agents.py`): `AgentDef` is pure metadata
  (name, mode, description, instructions, max_turns, optional model) —
  skene (primary) + code/schema (subagents). Toolset binding is by name
  in `core/tasks.py::_build_subagent_tools` because toolsets need per-run
  inputs; adding a subagent = registry entry + toolset binding (the task
  tool's description self-updates from the registry). `GET /agent` is
  live; `AgentInfo.model` is on the wire but no built-in agent sets it —
  honoring per-agent models is still a factory-side TODO (phase 5).
- **Concurrent tool dispatch**: `agent_loop.run_agent_stream` now runs a
  turn's tool calls concurrently — `ToolCallStarted` events in emitted
  order, `ToolCallFinished` in completion order, tool-result messages
  appended in emitted order (deterministic provider replays). The
  cooperative abort is checked before each LLM call and after each tool
  batch. This is what makes two `task` calls in one turn run subagents
  in parallel.
- **Run bookkeeping is centralized**: `SessionService.execute_run` owns
  the assistant message + running/aborted/error recording for every run
  kind. On success it leaves the session `running` and returns — the
  caller picks the terminal status (the canned journey run turns
  "finished without an artifact" into `session.error`).
- **Prompt dispatch**: `create_services` wires
  `SessionService.run_factory` → `core.journey.make_run_factory`.
  Sessions whose agent is a registered *primary* get the main-agent flow
  with workspace defaults (repo = workspace dir, no schema source);
  anything else falls back to the tool-less chat run.
- **Task tool** (`core/tasks.py`): creates the child session
  (`parent_id`), runs the subagent via `execute_run`, returns
  `{sessionId, agent, milestonesEmitted, turns, stoppedReason, summary}`
  as the tool result. Candidate milestones persist live as
  `MilestonePart`s in the *child* session. A failed toolset binding
  (e.g. no schema source) errors the tool call without creating a child.
- **MilestonePart is typed**: `milestone` is `CandidateMilestone`
  (camelCase on the wire: `proposedId`, `trackedEvent`, `stageId=null`
  pre-classification). `CandidateMilestone`/`Evidence` live in
  `skene/schema/milestone.py`; analyzers re-export. **Old dev DBs**: the
  phase-2 wrapper's milestone parts (final `Milestone` dumps) no longer
  validate — reading such a session 500s. Pre-1.0, by design (the doc
  said don't support both shapes); wipe `~/.local/share/skene/skene.db`
  if it bites.
- **finalize_journey** (`core/journey.py`): collects milestone parts
  from child sessions (bucket = `child.agent == "schema"` → schema,
  everything else → code), then specialize (unless disabled) → merge →
  classify → assemble → write yaml → `ArtifactPart` in the parent.
  Idempotent — a re-run overwrites the artifact.
- **Abort fans out**: `SessionService.abort` walks the child-session
  tree (parent first, then stored children), and the task handler's
  cancellation path aborts the child it is waiting on. Corollary:
  aborting a *child* session directly also takes down the parent's
  in-flight run (its `await` on the child raises CancelledError).
- **Parity + retirement**: the phase-2 wrapper, `pipeline.py`, and the
  `run_code_agent`/`run_schema_agent` runners are gone. The golden
  fixture `tests/fixtures/parity/journey.golden.yaml` was generated from
  the old pipeline with `tests.fakes.JourneyFakeLLM`;
  `test_journey_output_matches_pipeline_golden` pins the agentic flow to
  it. `db_url` introspection now happens lazily in
  `JourneyRunContext.schema_index()` (off-loop, never persisted).
- **Client contract for the TUI** (unchanged + extended):
  `POST /journey/analyse` → `{sessionId}`, progress on `/event`, child
  sessions via `GET /session/{id}/children`, milestones stream as
  `part.created` with `type=milestone` in child sessions, the finished
  run has an `artifact` part in the parent and `session.idle` /
  `session.error` on the bus. Canned sessions are `agent="skene"`.
  Still deferred to phase 5: `GET /provider`, `GET/PATCH /config`,
  permission asks.

### Phase 4 — pointers for the TUI cutover

Everything the cutover needs to know about the as-built server, in one
place:

- **Getting the spec / generating the client**: no CI job publishes it
  yet — add one (or a `tui/Makefile` target) that dumps the schema and
  runs `oapi-codegen`:
  `uv run python -c "import json; from skene.server import create_app; print(json.dumps(create_app().openapi()))" > openapi.json`
  (equivalently, `GET /doc` on a running server). The SSE `Event` union
  can't be derived from the streaming route, so `create_app` injects it
  by hand: it appears as `components.schemas.Event` (plus each concrete
  event model) and as the `text/event-stream` content schema of
  `GET /event` — the generated Go types cover events too; only the SSE
  *reader* is hand-written.
- **Server lifecycle**: `skene serve` listens on `127.0.0.1:4906` by
  default. Non-local binds require `--token` / `SKENE_SERVER_TOKEN`;
  clients then send `Authorization: Bearer <token>`. `/health`
  (`{status, version}`) is unauthenticated for probes. The server starts
  fine *without* LLM credentials — `POST /journey/analyse` returns 503
  with the reason, so the TUI can surface "configure credentials"
  instead of failing at spawn. The TUI may own the process (spawn
  `skene serve`, poll `/health`) or attach to a running one.
- **Workspace routing**: REST routes scope by `x-skene-directory`
  (fallback: the *server's* cwd — the TUI should always send the header).
  `GET /event` differs: with the header it delivers that workspace's
  events plus server-wide ones; without it the stream is unfiltered.
- **SSE framing**: `data: <event JSON>\n\n` frames only — no `event:` or
  `id:` lines. The first frame is `server.connected`; after 10 s of
  *silence* (not fixed cadence) a `server.heartbeat` is emitted. Event
  JSON is `{id, type, properties}` (`skene/schema/event.py`).
- **Rendering model**: messages and parts are upserts keyed by `id` —
  `message.updated` / `part.updated` carry the full replacement object,
  so a client can just overwrite. Tool parts transition
  `running → completed|error` via `part.updated`.
  `PartUpdated.properties.delta` is per-turn text, not token-level (see
  the phase-1 note). Milestone parts live in the *child* sessions: the
  TUI learns about subagents from `session.created` events whose
  `parentId` is set (or `GET /session/{id}/children`) and keys every
  message/part event by its `sessionId` to build the per-subagent
  progress tree that replaces stdout scraping.
- **The analyse flow**: `POST /journey/analyse` (body mirrors the CLI
  flags, camelCase) → `202 {sessionId}`; watch events until
  `session.idle` for that session (the `artifact` part carries the
  journey.yaml path) or `session.error` (`properties.error` is the
  message). Cancel = `POST /session/{id}/abort` — takes down the whole
  child tree.
- **Visualizer**: `GET /journey` returns the workspace's journey.yaml
  parsed to JSON (first match across the bundle dirs), 404 until a run
  has produced one — replaces the TUI reading the file itself.
- **No interactive prompts**: the journey flow never asks questions, so
  `engine.go`'s stdin-prompt machinery is deleted without replacement;
  the ask/answer flow arrives with phase 5's permissions.

### Phase 4 — as built (notes for phase 5+)

What exists after phase 4 (`feat/server-phase4`), and what the hardening
phase should know:

- **Generated client**: `tui/internal/api/client.gen.go` (oapi-codegen
  v2.5.0, models + client) from `tui/internal/api/openapi.json`.
  Regenerate with `make -C tui generate`. The checked-in spec is
  **downgraded to OpenAPI 3.0** by `tui/scripts/dump_openapi.py` because
  oapi-codegen can't consume FastAPI's 3.1 output: nullable `anyOf`
  collapses to `nullable: true`, and single-value-enum properties (the
  `type`/`role`/`status` discriminator literals) are force-marked
  `required` so the generated union helpers compile. The `Event` union
  came through without discriminator dispatch — `internal/api/sse.go`
  (`EventEnvelope.Decode`) does typed dispatch by peeking `type`; the
  part/tool-state unions kept their generated `Discriminator()` helpers.
  There is still no CI job — regeneration is manual when the API changes.
- **SSE reader**: `internal/api/sse.go` — `data:`-only framing per the
  contract, 16 MiB frame cap, unknown event types skipped (forward
  compatible). Unit-tested in `sse_test.go`.
- **Backend service** (`tui/internal/services/backend`): `Connect`
  attaches to `SKENE_SERVER_URL` (honouring `SKENE_SERVER_TOKEN`) or
  spawns `uvx <GrowthPackageSpec()> serve --port <free>` — env-driven
  LLM config (`SKENE_API_KEY/PROVIDER/MODEL/BASE_URL`), /health polled
  up to 120 s (cold uvx cache), last 30 output lines kept for error
  reports, `Stop()` = SIGINT then SIGKILL. `RunJourney` subscribes to
  `/event` *before* POSTing `/journey/analyse`, folds the stream into
  per-agent progress lines + three coarse phases via `runTracker`
  (which keys child sessions off `session.created.parentId` and ignores
  other session trees in the same workspace), and maps ctx cancellation
  to `POST /session/{id}/abort`. Live tests (`live_test.go`, env-gated:
  `SKENE_SERVER_URL`, `SKENE_LIVE_SPAWN`, `SKENE_LIVE_FULL`) cover
  attach, spawn, and a full end-to-end analysis.
- **TUI wiring**: the app owns one lazily-connected `backend.Server`
  (`ensureBackend`, mutex-guarded — also reached from visualizer HTTP
  handlers), stopped in `Cleanup()`. The journey visualizer serves
  `GET /journey` through that server; other dashboard files still read
  local files (`visualizer.NewFileServer`). Stdout parsing, the stall
  timer, and the stdin-prompt machinery (engine + `PromptMsg` +
  analyzing-view overlay) are gone.
- **Legacy commands still spawn uvx**: `analyze`, `plan`, `build`,
  `validate`, `push` run through a simplified line-streaming
  `growth.Engine` (display-only; no parsing). Moving them server-side
  is phase-5+ scope, as is per-run `schema_dir`/`db_url` input from the
  TUI (the analyse POST currently sends an empty body = workspace
  defaults).
- **Auto-publish gap**: the old TUI journey run appended
  `--auto-publish` for linked skene-provider workspaces. The server's
  `JourneyAnalyseRequest` has no such flag, so the cutover drops it —
  publish stays available as the explicit "Deploy to Skene Cloud" push
  step. If implicit publish should return, add it to the analyse route,
  not the client.

---

## 9. Resolved questions (2026-07-06)

- **Session retention: keep everything.** No GC; sessions are the debug trace for
  every analysis. Add a `skene sessions prune` command later if the DB ever becomes
  a problem, but don't build it now.
- **Multi-tenancy: not in scope.** Same posture as opencode: single-tenant server,
  per-server token, per-directory workspace scoping. One global SQLite under one OS
  user; Skene Cloud stays a separate service the client pushes to. "One shared
  server, many users" is explicitly a non-goal — if that ever changes it's a
  redesign of auth/storage, not a bolt-on.
- **Interactive main agent: start with the canned prompt.** v1 clients only trigger
  the canned analyse prompt; no free-form chat with the skene agent. The API
  (`POST /session/{id}/message`) already supports arbitrary follow-up messages, so
  enabling chat later is TUI/CLI scope, not a server change.
