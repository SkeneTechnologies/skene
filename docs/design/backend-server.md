# Skene Backend Server — Design

Status: in progress (2026-07-06) — phase 1 implemented, phases 2-5 pending.
Work lands on feature branches targeting the `v1.0` integration branch.

| Phase | Status | Where |
|---|---|---|
| 1. Schema + streaming loop | **done** | `feat/server-phase1` |
| 2. Server MVP | pending | |
| 3. Agentic flow | pending | |
| 4. TUI cutover | pending | |
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
| Permission `ask` flow (tool pauses, client answers via HTTP) | **Take** (phase 2) | Needed for db-write tools later |
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
