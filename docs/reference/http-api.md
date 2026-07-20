# HTTP API Reference

The skene backend server (started with [`skene serve`](cli.md#serve)) exposes a REST + SSE API. The CLI's remote mode and the TUI are both clients of this API; you can use it directly to build your own integrations.

- **Base URL:** `http://127.0.0.1:4906` by default.
- **OpenAPI spec:** `GET /doc` (alias of `/openapi.json`). The SSE `Event` union is injected into the spec, so generated clients get typed event models. FastAPI's interactive docs are available at `/docs` and `/redoc`.
- **Authentication:** if the server was started with a token, send `Authorization: Bearer <token>` on every request. `/health`, `/doc`, and the OpenAPI/docs endpoints are always unauthenticated. Auth is single-tenant — one optional token per server; multi-tenancy is out of scope.
- **Workspaces:** all REST routes scope to a workspace (project directory) via the `x-skene-directory` header. Without the header, REST routes fall back to the server's working directory. The `/event` stream is the exception: with the header it filters to that workspace, without it it streams events for **all** workspaces.

## Routes

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/event` | SSE stream of server events (see [Events](#events)) |
| `POST` | `/session` | Create a session `{agent?, parentId?, title?}` → `201` |
| `GET` | `/session` | List sessions (workspace-scoped) |
| `GET` | `/session/{id}` | Get one session |
| `GET` | `/session/{id}/children` | Child sessions (subagent runs) |
| `GET` | `/session/{id}/message` | Messages with their parts |
| `POST` | `/session/{id}/message` | Prompt the session → `202` with the created user message; the run is async — watch `/event`. `409` if the session is already running. |
| `POST` | `/session/{id}/abort` | Cancel the session and its whole child-session tree → `{"aborted": bool}` |
| `GET` | `/session/{id}/permissions` | Permission asks raised by the session |
| `POST` | `/session/{id}/permissions/{permID}` | Answer an ask: `{"reply": "allow" \| "deny"}` |
| `GET` | `/agent` | Agent registry (primary agent + subagents) |
| `GET` | `/provider` | Supported LLM providers, active one marked |
| `GET` | `/config` | Resolved server config, secrets redacted (read-only — there is no config-mutation API) |
| `POST` | `/journey/analyse` | Start a canned journey analysis → `202 {"sessionId": ...}`; `503` if the server has no LLM credentials |
| `GET` | `/journey` | The workspace's `journey.yaml` as JSON (`404` if none exists yet) |
| `GET` | `/health` | `{"status": "ok", "version": ...}` — always unauthenticated |

## Domain model

**Session** — one agent run. Fields include `status` (`idle` | `running` | `error`) and `parentId`: a subagent run is a child session linked to its parent, so a journey analysis is a session tree. Aborting a parent cancels the entire tree.

**Message** — belongs to a session; role is `user`, `assistant`, or `synthetic`.

**Part** — a piece of message content. Types: `text`, `reasoning`, `tool`, `feature`, `artifact`. Tool parts carry streaming state (`running` → `completed` | `error`). During journey analysis, features stream as `feature` parts in the child sessions, and the finished run puts `artifact` parts (the written `features.yaml` and `journey.yaml`) in the parent session.

Messages and parts are **upserts keyed by id** — on a `*.updated` event, clients just overwrite their copy.

### Agents

`GET /agent` lists the registry: `skene` (primary — orchestrates a run) plus the `code` and `schema` subagents. The primary agent spawns subagents through a `task` tool; multiple `task` calls in one turn run subagents in parallel. Agent definitions may carry a per-agent `model` override, honoured when the server's LLM factory supports it.

## Events

`GET /event` is a Server-Sent Events stream. Frames use `data:`-only framing, one JSON object per frame, shaped `{id, type, properties}`. A heartbeat is sent after 10 seconds of silence.

| Event type | Meaning |
|------------|---------|
| `server.connected` | Stream opened |
| `server.heartbeat` | Keep-alive (after 10s of silence) |
| `session.created` / `session.updated` | Session lifecycle; watch `status` |
| `session.idle` | Run finished |
| `session.error` | Run failed |
| `message.created` / `message.updated` | Message upserts |
| `part.created` / `part.updated` | Part upserts (tool state, streaming text deltas, features, artifacts) |
| `permission.asked` / `permission.answered` | Permission flow (see below) |

## Permissions

The permission flow (`GET/POST /session/{id}/permissions*` plus the `permission.*` events) is the mechanism for guarded operations — a run pauses, raises an ask, and resumes once a client answers `allow` or `deny`. Answers are one-shot and there is no timeout; aborting a run auto-denies its pending asks.

No built-in tool raises asks yet — the mechanism exists end-to-end for future guarded operations (for example database writes).

## Typical flow: run a journey analysis

```bash
# 1. Open the event stream for your workspace (keep it running)
curl -N -H "x-skene-directory: /path/to/project" http://127.0.0.1:4906/event

# 2. Start the analysis
curl -X POST -H "x-skene-directory: /path/to/project" \
     -H "content-type: application/json" -d '{}' \
     http://127.0.0.1:4906/journey/analyse
# → 202 {"sessionId": "..."}

# 3. Watch session/message/part events stream; the run is done on session.idle

# 4. Fetch the result
curl -H "x-skene-directory: /path/to/project" http://127.0.0.1:4906/journey
```

## Storage

Every session is persisted in a global SQLite database (WAL mode) at `~/.local/share/skene/skene.db`, overridable with `SKENE_DB_PATH` or `skene serve --db-path`. It holds sessions for every workspace; retention is keep-everything (no GC command yet).

> **Pre-1.0 caveat:** the feature/milestone wire shape changed during development — old dev databases can return `500` on read. Deleting the DB file fixes it.
