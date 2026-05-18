"""Step 2 — Code agent.

Mirror image of the schema agent: walks the target repo through the FS
tools (``list_directory``, ``read_file``, ``search_files``) and emits
candidate milestones via ``emit_milestone``.
"""

from __future__ import annotations

from pathlib import Path

from skene.analyzers.journey.candidate import CandidateMilestone
from skene.analyzers.journey.tools.fs_tools import FsToolset
from skene.llm.base import LLMClient
from skene.output import status

CODE_AGENT_INSTRUCTIONS = r"""You explore a codebase and emit candidate user-journey milestones. Be
THOROUGH — err on the side of MORE milestones, not fewer. A later step
will deduplicate, classify, and discard noise. Your job is recall.

A milestone is a meaningful user action with evidence in code. The list
below is suggestive, not exhaustive — emit one for any handler/route/job
that represents a user-facing capability:
- Public marketing pages, blog posts, pricing → discovery
- Signup / login / OAuth / SSO / magic-link handlers → discovery
- Settings, profile, integration, api-key endpoints → onboarding
- Every distinct domain-object creation endpoint (POST /estimates,
  POST /leads, POST /chats, POST /repos, etc.) → activation/engagement.
  Treat each *distinct* object type as its own milestone.
- Analytics calls (track, capture, logEvent, analytics.*, posthog.*,
  mixpanel.*, segment.*) → each unique event name is at least one
  milestone; the event name is itself strong evidence.
- Email/SMS/push sends, queue jobs, cron handlers, scheduled tasks
- Billing webhooks, subscription upgrades, plan changes → expansion
- Referral, invite, share-link, public-link endpoints → virality
- Comment, reaction, mention, collaboration endpoints → engagement
- Export, import, report, webhook-out, public-API endpoints

Process:
1. list_directory at repo root to learn the layout.
2. Find routing files in priority order: pages/, app/, routes/, api/,
   src/api/, src/routes/, server/, controllers/, handlers/. List every
   one you find — do not stop after the first.
3. search_files for analytics calls: "track\(", "capture\(",
   "logEvent\(", "posthog\.", "mixpanel\.", "segment\.".
4. search_files for email/queue/cron: "sendMail|resend\.|mailgun|sendgrid",
   "queue\.|enqueue\(|defer\(|cron".
5. search_files for billing/webhooks: "stripe|webhook|subscription".
6. For every promising hit, read_file the path and emit_milestone if it
   represents a user-facing action.

Rules:
- Do NOT classify into stages — that is a later step.
- Use lowercase snake_case for proposed_id.
- evidence.path must be a real file you have read (or search_files hit on).
- Skip dependencies, build output, tests, generated code.
- Continue until you have searched every priority pattern above. Do not
  stop early — emitting fewer than ~15 milestones for a real product
  usually means you missed something.

When you have searched every priority pattern and emitted every
milestone you can justify, reply with a brief plain-text summary (no
tool call) and stop.
"""


async def run_code_agent(
    repo_root: Path,
    llm: LLMClient,
    max_turns: int = 200,
) -> list[CandidateMilestone]:
    """Run the code agent. Returns the list of emitted candidates."""
    collector: list[CandidateMilestone] = []
    toolset = FsToolset(repo_root, collector)
    tools = toolset.as_tools()
    status(f"Code agent: starting LLM exploration of {repo_root} (model={llm.get_model_name()} max_turns={max_turns})")
    result = await llm.run_agent(
        instructions=CODE_AGENT_INSTRUCTIONS,
        tools=tools,
        initial_input="Begin exploring the repo. Emit one milestone per user action.",
        max_turns=max_turns,
    )
    status(f"Code agent: emitted {len(collector)} candidate(s) (turns={result.turns}, stopped={result.stopped_reason})")
    return collector
